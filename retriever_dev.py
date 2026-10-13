# -*- coding: utf-8 -*-
"""
Created on Wed Sep 30 13:04:42 2026

@author: sabri
"""

"""
retriever.py - Poll an FTP directory and retrieve expected input files.

The program maintains two lists, stored as plain text files with one
filename per line:

    expected.txt   - files we expect to receive (maintained by a person)
    retrieved.txt  - files we have already downloaded (updated by this program)

On every poll, any file that is on the expected list but NOT on the
retrieved list is downloaded from the FTP server (if it has arrived yet),
and the retrieved list is updated.

Examples (run from a terminal / Anaconda Prompt):
    python retriever.py --host 127.0.0.1 --port 2121
    python retriever.py --host 127.0.0.1 --port 2121 --once
    python retriever.py --help
"""

import argparse                         # reads command-line options
import os                               # paths, folders, file checks
import time                             # sleep between polls
from datetime import datetime           # timestamps for log messages
from ftplib import FTP, all_errors, error_perm   # built-in FTP client
import shutil                          #rest file settings (for test)
import threading                       #manages function call timing

# --------------------------------------------------------------------------
# Logging helper
# --------------------------------------------------------------------------
#%%
def log(message):
    """Print a message with a timestamp in front of it."""
    # flush=True makes the text appear immediately, even when the output
    # is being redirected to a log file.
    return print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)

log("This is what log does.")


#%%
# --------------------------------------------------------------------------
# List management (stored as text files)
# --------------------------------------------------------------------------
def load_list(path):
    """Read file contain a list of filenames and return filenames as a set.

    Blank lines and lines starting with '#' are ignored.
    A missing file counts as an empty list.
    """

    if not os.path.exists(path):            # os.path.exists is True if the file is there, False otherwise.
        return set()             # No file yet -> nothing in the list. set() is an empty set.
    file_list = set()            #create set to fill
    with open(path) as f:                   #open and close file after reading
        for line in f:
            name = line.strip()             # remove spaces and the newline
            if name and not name.startswith("#"): #ignore lines starting with '#'
                file_list.add(name)
    return file_list

#print("Expected list:", load_list("expected.txt"))

def save_list(path, file_list):
    """Write a set of filenames to `path`, one per line, sorted."""
   
    temp_path = path + ".tmp"            # Write to a temporary file first, so if program crashes mid-write, the old list is still intact.
    with open(temp_path, "w") as f:
        for name in sorted(file_list):
            f.write(name + "\n")
    os.replace(temp_path, path)             # swap in one step
    return
#save_list("test_list.txt", {"b.csv", "a.csv"})      # write...
#print("File contents:\n" + open("test_list.txt").read())
#assert load_list("test_list.txt") == {"a.csv", "b.csv"}   # ...and read back

#test load_list and save_list together
#save_list("test_list.txt", load_list("expected.txt"))
#print("File contents:\n" + open("test_list.txt").read())
#assert load_list("test_list.txt") == {"data_a.csv", "data_b.csv", "data_c.csv"}

#%%
# --------------------------------------------------------------------------
# Compare Lists
# --------------------------------------------------------------------------

def find_files_to_fetch(expected, retrieved, remote):
    """Decide what to download. Returns two sets:
        ready   - expected, not yet retrieved, and on the server
        waiting - expected, not yet retrieved, but NOT on the server yet"""
    outstanding = expected - retrieved       # still need these (- is set difference "in the first but not the second")
    ready = outstanding & remote             # ...and they're available (& is set intersection "in both")
    waiting = outstanding - remote           # ...but haven't arrived
    return ready, waiting


#test find files
#expected  = {"data_a.csv", "data_b.csv", "data_c.csv"}
#retrieved = {"data_a.csv"}
#remote    = {"data_a.csv", "data_b.csv", "unrelated.txt"}
#ready, waiting = find_files_to_fetch(expected, retrieved, remote)
#print("ready:  ", ready)
#print("waiting:", waiting)
#assert ready == {"data_b.csv"}        # a is done, c isn't there, unrelated isn't expected
#assert waiting == {"data_c.csv"}

# Edge case: everything already retrieved means nothing to do.
#assert find_files_to_fetch({"x"}, {"x"}, {"x"}) == (set(), set())
#log("Edge case Test passed")

#%%
# --------------------------------------------------------------------------
# Connecting and Listing Remote Files
# --------------------------------------------------------------------------

def connect_ftp(host, port, user, password, remote_dir, timeout=30):
    """Connect and log in to the FTP server, then change to remote_dir."""
    ftp = FTP()
    ftp.connect(host, port, timeout)      # give up after 30s of silence
    ftp.login(user, password)
    ftp.cwd(remote_dir)                      # "cd" on the server
    return ftp

#need to start a server to test: python -m pyftpdlib -p 2121 -d ftp_root
#ftp = connect_ftp("127.0.0.1", 2121, "anonymous", "", "/") #"127.0.0.1" code for localhost
#print("Server says:", ftp.getwelcome()) #FTP server greeting message upon connection "getwelcome()" returns that as a string

def close_ftp(ftp):
    """Close the FTP connection, even if it's already broken."""
    try:
        ftp.quit()                           # easy close
    except all_errors:
        ftp.close()                          # connection is dead; just close our end


def list_remote_files(ftp):
    """Return the set of names in the server's current directory."""
    try:
        names = ftp.nlst()                   # NLST = "name list" is an FTP command
    except error_perm as e:             #avoid empty file error and treat empty list as "no files"
        if str(e).startswith("550"):        # Some servers answer an empty folder with error 550
            print("Expected error:", e)
            return set()
        raise
    return {os.path.basename(name) for name in names} # Ensure only filenames are retruned, not full path.

#ftp = connect_ftp("127.0.0.1", 2121, "anonymous", "", "/")
#remote = list_remote_files(ftp)
#print("Remote files:", sorted(remote))
#close_ftp(ftp)
#assert remote == {"data_a.csv", "data_b.csv", "unrelated.txt"}
#log("Connected and gathered remote list successfully")

#%%
# --------------------------------------------------------------------------
# Download File
# --------------------------------------------------------------------------

def download_file(ftp, filename, local_dir):
    """Download one file from the server into local_dir. Return its path.
    Note: a .part (partial download) is used first so that if the network drops 
    before completing the download a truncated .csv isn't returned
    """
    local_path = os.path.join(local_dir, filename)
    temp_path = local_path + ".part"         # .part first
    try:
        with open(temp_path, "wb") as f:     # "wb" = write binary (exact bytes) to temp .part
            # RETR asks the server for the file. The server sends it in
            ftp.retrbinary("RETR " + filename, f.write) # RETR asks the server for the file. The server sends it in
    except Exception:                           # Ensure a half-downloaded file isn't left
        if os.path.exists(temp_path):
            os.remove(temp_path)                
        raise                                # re-raise so the caller knows
    os.replace(temp_path, local_path)       # Assign real name once download is finished completely
    return local_path

#test download
#os.makedirs("retrieved_files", exist_ok=True) #create file folder incase it doesn't exist
#ftp = connect_ftp("127.0.0.1", 2121, "anonymous", "", "/")
#test for file that exists:
#print("Saved to:", path)
#print("Contents:", open(path).read())
#assert os.path.isfile(path)
#log("Downloaded Successfully")
#test file that doesn't exist (should raise an error AND leave no .part file)
#try:
    #download_file(ftp, "nope.csv", "retrieved_files")
#except error_perm as e:
    #print("Expected error:", e)
#assert not os.path.exists(os.path.join("retrieved_files", "nope.csv.part"))
#close_ftp(ftp)

#%% 
# --------------------------------------------------------------------------
# Combine functions for complete poll
# --------------------------------------------------------------------------

def poll_once(settings):
    """Do one check: download outstanding expected files.
    Returns the set of filenames downloaded during this poll."""
    
    expected = load_list(settings["expected"]) # Re-read both lists every poll, so edits to expected.txt take effect without restarting the program
    retrieved = load_list(settings["retrieved"])

    if not (expected - retrieved):              #Avoide contacting server if no new files to retrieve
        log("Nothing outstanding - all expected files have been retrieved.")
        return set()

    os.makedirs(settings["local_dir"], exist_ok=True)               #make dir for to download to
    log(f"Connecting to {settings['host']}:{settings['port']} ...") #note connection start time
    ftp = connect_ftp(settings["host"], settings["port"], settings["user"], settings["password"], settings["remote_dir"])

    newly_retrieved = set() #create empty set to fill
    try:
        remote = list_remote_files(ftp) #get list of remote files for comparison
        ready, waiting = find_files_to_fetch(expected, retrieved, remote) #decide what to fetch

        for filename in sorted(ready):
            try:
                download_file(ftp, filename, settings["local_dir"]) #download expected file, not yet retrieved, and on the server
            except all_errors as e:         #don't allow bad file to stop downloads
                log(f"FAILED to retrieve {filename}: {e}") #note failed download 
                continue
            retrieved.add(filename) #immediately update retrieved list so crash later in this poll doesn't lose track of this file
            save_list(settings["retrieved"], retrieved)
            newly_retrieved.add(filename) #add file to newly_retrieved set to return 
            log(f"Retrieved {filename}")

        if waiting:                     
            log(f"Expected file not found on server: {', '.join(sorted(waiting))}")     #note expected file, not yet retrieved, but NOT on the server yet
    finally:                     # 'finally' runs no matter what
        close_ftp(ftp)          #make sure connection closes

    return newly_retrieved


#%%
#Test complete poll 
#Reset file settings for fresh start
shutil.rmtree("retrieved_files", ignore_errors=True)   # delete downloads folder
if os.path.exists("retrieved.txt"):
    os.remove("retrieved.txt")                          # delete retrieved list
print("Reset done")

#define settings dictionary 
test_settings = {
    "host": "127.0.0.1", "port": 2121,
    "user": "anonymous", "password": "",
    "remote_dir": "/",
    "local_dir": "retrieved_files",
    "expected": "expected.txt",
    "retrieved": "retrieved.txt",
}

print("--- first poll ---")
print("Returned:", poll_once(test_settings))
print("--- second poll ---")
print("Returned:", poll_once(test_settings))

print("\nretrieved.txt now contains:\n" + open("retrieved.txt").read())
assert load_list("retrieved.txt") == {"data_a.csv", "data_b.csv"}
log("Test complete poll_once successfully")

#%%
# --------------------------------------------------------------------------
# Continuous Poll on Schedule
# --------------------------------------------------------------------------
def continuous_poll(settings, interval, max_polls=None):
    """Call poll_once every `interval` seconds.
    max_polls limits the number of polls (handy for testing);
    None means run until stopped with Ctrl+C."""
    log(f"Starting. Continuous polling every {interval} seconds. Press Ctrl+C to stop.")
    polls = 0 #count polls
    try:
        while max_polls is None or polls < max_polls:   #continue polling until max 
            polls += 1
            try:
                poll_once(settings)
            except all_errors as e:         #Prevent crashing when server down, network blip, bad login, etc
                log(f"Poll failed: {e}")    #Note error and try poll and continue to next poll
            if max_polls is None or polls < max_polls:   #Wait before the next poll (skip the wait after the last one)
                time.sleep(interval) 
            log(f"Completed polls: {polls}") #Note poll count
    except KeyboardInterrupt:               #end polling when user interupts 
        log("Stopped by user.")             #Note end
    

#%%
#test continous polling
continuous_poll(test_settings, interval=2)    # polls at ~0, 2, 4, 6 seconds
assert load_list("retrieved.txt") == {"data_a.csv", "data_b.csv"}

#%%
#test continous polling with file arrival 
#Reset file settings for fresh start
shutil.rmtree("retrieved_files", ignore_errors=True)   # delete downloads folder
if os.path.exists("retrieved.txt"):
    os.remove("retrieved.txt") 
if os.path.exists("ftp_root/data_c.csv"):
    os.remove("ftp_root/data_c.csv")                         # delete retrieved list
print("Reset done")

def file_arrives():
    """Simulate someone uploading data_c.csv to the server."""
    with open(os.path.join("ftp_root", "data_c.csv"), "w") as f:
        f.write("id,value\n3,300\n")
    print("  >>> (simulation) data_c.csv arrived on the server")
threading.Timer(3, file_arrives).start()          # run file_arrives() in 3 seconds

continuous_poll(test_settings, interval=2, max_polls=4)    # polls at ~0, 2, 4, 6 seconds

assert load_list("retrieved.txt") == {"data_a.csv", "data_b.csv", "data_c.csv"}
log("Continous polling successfull")


