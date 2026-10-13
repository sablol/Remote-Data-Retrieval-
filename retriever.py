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
retrieved list is downloaded from the FTP server (if it is present on the server),
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


# --------------------------------------------------------------------------
# Log Messages
# --------------------------------------------------------------------------
def log(message):
    """Print a message with a timestamp in front of it."""
    #flush=True makes the text appear immediately, even when the output
    #is being redirected to a log file.
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


# --------------------------------------------------------------------------
# List management (stored as text files)
# --------------------------------------------------------------------------
def load_list(path):
    """Read a list file and return its filenames as a set.

    Blank lines and lines starting with '#' are ignored.
    A missing file counts as an empty list.
    """
    if not os.path.exists(path):            #os.path.exists is True if the file is there, False otherwise.
        return set()             #no file yet, return empty set 
    file_list = set()            #create set to fill
    with open(path) as f:                   #open and close file after reading
        for line in f:
            name = line.strip()             #remove spaces and the newline
            if name and not name.startswith("#"): #ignore lines starting with '#'
                file_list.add(name)
    return file_list



def save_list(path, file_list):
    """Write a set of filenames to `path`, one per line, sorted."""
   
    temp_path = path + ".tmp"            #write to a temporary file first, so if program crashes mid-write, the old list is still intact.
    with open(temp_path, "w") as f:
        for name in sorted(file_list):      #sort names to write 
            f.write(name + "\n")            #one filename per line
    os.replace(temp_path, path)             #swap in one step
    
# --------------------------------------------------------------------------
# Compare Lists
# --------------------------------------------------------------------------
def find_files_to_fetch(expected, retrieved, remote):
    """Decide what to download. Returns two sets:
        ready   - expected, not yet retrieved, and on the server
        waiting - expected, not yet retrieved, but NOT on the server yet"""
    outstanding = expected - retrieved       #files still needed (- is set difference "in the first but not the second")
    ready = outstanding & remote             #files still needed and are available on server (& is set intersection "in both")
    waiting = outstanding - remote           #files still needed but not on server 
    return ready, waiting


# --------------------------------------------------------------------------
# FTP functions - Connecting and Listing Remote Files
# --------------------------------------------------------------------------
def connect_ftp(host, port, user, password, remote_dir, timeout=30):
    """Connect and log in to the FTP server, then change to remote_dir."""
    ftp = FTP()
    ftp.connect(host, port, timeout)      #give up after 30s of silence
    ftp.login(user, password)               #allow for password protection case
    ftp.cwd(remote_dir)                      #"cd" on the server
    return ftp


def close_ftp(ftp):
    """Close the FTP connection, even if it's already broken."""
    try:
        ftp.quit()                           #close connection to the server
    except all_errors:  
        ftp.close()                          #for any error assume connection is dead; close our end


def list_remote_files(ftp):
    """Return the set of names in the server's current directory."""
    try:
        names = ftp.nlst()                   #"NLST" FTP command to name list
    except error_perm as e:             #catch ftp server errors 
        if str(e).startswith("550"):        #expected error: empty file error (550) 
            print("Expected error:", e)
            return set()                    #treat empty list as "no files"
        raise                               #for all other errors stop function and pass on error
    return {os.path.basename(name) for name in names} #ensure only filenames are retruned, not full path.


def download_file(ftp, filename, local_dir):
    """Download one file from the server into local_dir. Return its path.
    Note: a .part (partial download) is used first so that if the network drops 
    before completing the download a truncated .csv isn't returned
    """
    local_path = os.path.join(local_dir, filename)
    temp_path = local_path + ".part"         #.part first
    try:
        with open(temp_path, "wb") as f:     #"wb" = write binary (exact bytes) to temp .part
            ftp.retrbinary("RETR " + filename, f.write) #"RETR" retrieve file from server and write locally
    except Exception:                           #for any error while downloading
        if os.path.exists(temp_path):
            os.remove(temp_path)                #remove half-downloaded file isn't left
        raise                                #stop function and pass on error
    os.replace(temp_path, local_path)       #assign real name once download is finished completely
    return local_path


# --------------------------------------------------------------------------
# Combine functions for one poll
# --------------------------------------------------------------------------
def poll_once(settings):
    """Do one check: download outstanding expected files.

    `settings` is a dict with keys: host, port, user, password,
    remote_dir, local_dir, expected, retrieved.
    Returns the set of filenames downloaded during this poll.
    """
    expected = load_list(settings["expected"]) #re-read both lists every poll, so edits to expected.txt take effect without restarting the program
    retrieved = load_list(settings["retrieved"])

    if not (expected - retrieved):              #avoide contacting server if no new files to retrieve
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
            except all_errors as e:         #catch bad file 
                log(f"FAILED to retrieve {filename}: {e}") #note failed download 
                continue                    #don't allow bad file to stop downloads
            retrieved.add(filename) #immediately update retrieved list so crash later in this poll doesn't lose track of this file
            save_list(settings["retrieved"], retrieved)
            newly_retrieved.add(filename) #add file to newly_retrieved set to return 
            log(f"Retrieved {filename}")

        if waiting:                     
            log(f"Expected file not found on server: {', '.join(sorted(waiting))}")     #note expected file, not yet retrieved, but NOT on the server yet
    finally:                     #'finally' runs no matter what
        close_ftp(ftp)          #make sure connection closes

    return newly_retrieved

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
            except all_errors as e:         #prevent crashing when server down, network blip, bad login, etc
                log(f"Poll failed: {e}")    #Note error and try poll and continue to next poll
            if max_polls is None or polls < max_polls:   #wait before the next poll (skip the wait after the last one)
                time.sleep(interval) 
            log(f"Completed polls: {polls}") #Note poll count
    except KeyboardInterrupt:               #end polling when user interupts 
        log("Stopped by user.")             #Note end
    

# --------------------------------------------------------------------------
# Main command line program
# --------------------------------------------------------------------------
def main():
    """Read command-line options and start the program."""
    parser = argparse.ArgumentParser(description="Poll an FTP directory and retrieve expected input files.")

    #each add_argument defines one option
    parser.add_argument("--host", required=True, help="FTP server address")
    parser.add_argument("--port", type=int, default=21, help="FTP port (default 21)")
    parser.add_argument("--user", default="anonymous", help="FTP username")
    parser.add_argument("--password", default=os.environ.get("FTP_PASSWORD", ""),
                        help="FTP password (or set the FTP_PASSWORD environment variable)")
    parser.add_argument("--remote-dir", default="/", help="folder on the server to watch")
    parser.add_argument("--local-dir", default="retrieved_files", help="where downloaded files are saved")
    parser.add_argument("--expected", default="expected.txt", help="expected-files list")
    parser.add_argument("--retrieved", default="retrieved.txt", help="retrieved-files list")
    parser.add_argument("--interval", type=int, default=300, help="seconds between polls (default 300 = 5 minutes)")
    parser.add_argument("--once", action="store_true", help="poll a single time and exit")
    args = parser.parse_args()

    settings = vars(args) #turns argparse's result into a plain dict for poll_once expected call format

    if not os.path.exists(settings["expected"]):        #check if expected file exists
        log(f"WARNING: expected list {settings['expected']!r} not found - "
            "nothing will be retrieved until it exists.")       

    if args.once:       #option to run poll_once for testing
        try:
            poll_once(settings)
        except all_errors as e:             #end on error and report
            log(f"Poll failed: {e}")
    else:
        continuous_poll(settings, args.interval)    #default run forever


# Command line entry point (python retriever.py). Note: does not run when it's imported by another file.
if __name__ == "__main__":
    main()