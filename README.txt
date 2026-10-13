==========================================================================
 RETRIEVER.PY - FTP Expected-File Retriever
==========================================================================

PURPOSE
------------
retriever.py is a command-line program that watches a directory on an
FTP server and downloads the files from that server if they are named on 
a locally stored list of expected files.

It maintains two lists, each stored locally as a plain text file with one
filename per line:

  expected.txt   Files you expect to receive. YOU maintain this list.
  retrieved.txt  Files already downloaded. The PROGRAM maintains this list.

Every 5 minutes (by default) the program:
  1. Reads both lists.
  2. Works out which files are expected but not yet retrieved.
  3. Connects to the FTP server and downloads any of those files that
     are present on the server.
  4. Adds each successfully downloaded file to retrieved.txt.
  5. Reports any expected files that have not arrived on the server yet.

Files on the server that are NOT on the expected list are ignored.


REQUIREMENTS
------------
  - Python 3.8 or newer.
  - No extra packages are needed to RUN the program; it uses only
    Python's built-in modules (ftplib, argparse, os, time, datetime).
  - For TESTING on your own computer you need the pyftpdlib package,
    which provides a small practice FTP server:

        pip install pyftpdlib


PROJECT FILES
-------------
  retriever.py      The program.
  expected.txt      List of expected filenames (you create this).
  retrieved.txt     List of retrieved filenames (created automatically).
  retrieved_files\  Folder where downloads are saved (created automatically).

While running, you may briefly see these temporary files:
  retrieved.txt.tmp   The list being saved (renamed when complete).
  <filename>.part     A download in progress (renamed when complete).


SETTING UP THE EXPECTED LIST
----------------------------
Create a text file named expected.txt in the same folder as
retriever.py, with one filename per line. Blank lines are ignored, and
lines starting with # are treated as comments. Example (made up):

    # MOPITT data files
    AAOE_SONDES_DATA1.csv
    AAOE_SONDES_DATA2.csv
    ASDC_AAOE_OBS.xlsx

You can edit expected.txt while the program is running. Changes are
picked up at the next poll; there is no need to restart.

Filenames must match the server's filenames exactly, including
upper/lower case and the file extension.


HOW TO RUN
----------
Open a terminal (Anaconda Prompt on Windows, Terminal on Mac), change to
the project folder, and run:

    python retriever.py --host <server address> [options]

To stop the program, press Ctrl+C in the terminal window.

OPTIONS
  --host HOST          FTP server address. REQUIRED.
  --port PORT          FTP port. Default: 21
  --user USER          FTP username. Default: anonymous
  --password PASS      FTP password. Default: empty, or the value of the
                       FTP_PASSWORD environment variable if it is set.
  --remote-dir DIR     Folder on the server to watch. Default: /
  --local-dir DIR      Folder to save downloads in. Default: retrieved_files
  --expected FILE      Expected-files list. Default: expected.txt
  --retrieved FILE     Retrieved-files list. Default: retrieved.txt
  --interval SECONDS   Time between polls. Default: 300 (5 minutes)
  --once               Poll a single time, then exit.
  --help               Show the list of options and exit.

EXAMPLES
  Show help:
      python retriever.py --help

  Normal use, polling every 5 minutes:
      python retriever.py --host ftp.example.com --user sab --remote-dir /incoming

  Check once and exit:
      python retriever.py --host ftp.example.com --user sab --once

  Save downloads to a different folder:
      python retriever.py --host ftp.example.com --local-dir C:\data\inputs

SAMPLE OUTPUT
-------------
    [2026-09-30 14:08:12] Starting. Polling every 300 seconds. Press Ctrl+C to stop.
    [2026-09-30 14:08:12] Connecting to ftp.example.com:21 ...
    [2026-09-30 14:08:12] Retrieved data_a.csv
    [2026-09-30 14:08:13] Retrieved data_b.csv
    [2026-09-30 14:08:13] Expected file not found on server: data_c.csv
    [2026-09-30 14:13:13] Connecting to ftp.example.com:21 ...
    [2026-09-30 14:13:13] Retrieved data_c.csv
    [2026-09-30 14:18:13] Nothing outstanding - all expected files have been retrieved.

If every expected file has already been retrieved, the program does not
contact the server at all; it just reports "Nothing outstanding".

To keep a record of the output, redirect it to a log file:

    python retriever.py --host ftp.example.com >> retriever.log


==========================================================================
 PROGRAM CREATION & TESTING
==========================================================================

All functions within retriever.py, apart from the main function, can be 
found with development notes and print tests in retriever_dev.py. 

This program was developed and tested using a practice FTP server. You 
can test everything on your own computer by running a practice FTP
server. You will need TWO terminal windows: one for the server and one
for the program.

STEP 1 - CREATE TEST FILES
  In your project folder, create:

  a) A folder named ftp_root containing three small files:
         data_a.csv
         data_b.csv
         unrelated.txt
     (Any contents will do, e.g. "id,value" on one line.)

  b) A file named expected.txt containing:
         data_a.csv
         data_b.csv
         data_c.csv

  This set-up deliberately covers three cases:
     data_a.csv, data_b.csv  expected AND on the server -> should download
     data_c.csv              expected but NOT on server -> should wait
     unrelated.txt           on server but NOT expected -> should be ignored

STEP 2 - START THE PRACTICE SERVER (terminal window 1)
  Change to the project folder and run:

      python -m pyftpdlib -p 2121 -d ftp_root

  This shares the ftp_root folder on port 2121 with anonymous, read-only
  access. Leave this window open. If your firewall asks, allowing access
  on private networks is fine. Stop the server later with Ctrl+C.

STEP 3 - RUN THE TESTS (terminal window 2)
  Change to the project folder and work through these tests in order.

  TEST 1: First poll downloads the expected files
      python retriever.py --host 127.0.0.1 --port 2121 --once

      Expected result:
        - "Retrieved data_a.csv" and "Retrieved data_b.csv"
        - "Expected file not found on server: data_c.csv"
        - retrieved_files\ contains data_a.csv and data_b.csv
        - retrieved.txt lists data_a.csv and data_b.csv
        - unrelated.txt was NOT downloaded

  TEST 2: Second poll downloads nothing new
      python retriever.py --host 127.0.0.1 --port 2121 --once

      Expected result:
        - No "Retrieved" lines
        - "Expected file not found on server: data_c.csv"

  TEST 3: A late file is picked up while polling
      python retriever.py --host 127.0.0.1 --port 2121 --interval 10

      While it runs, create a file named data_c.csv inside ftp_root.
      Expected result: within about 10 seconds you see
      "Retrieved data_c.csv", and the poll after that says
      "Nothing outstanding". Press Ctrl+C to stop.

  TEST 4: Edits to expected.txt are picked up without a restart
      Start the program again with --interval 10. While it runs:
        a) add data_d.csv to expected.txt  -> "Still waiting for: data_d.csv"
        b) create data_d.csv in ftp_root   -> "Retrieved data_d.csv"
      Press Ctrl+C to stop.

  TEST 5: The program survives the server being down
      Stop the server (Ctrl+C in window 1). Add another name to
      expected.txt so something is outstanding, then run:

          python retriever.py --host 127.0.0.1 --port 2121 --interval 10

      Expected result: "Poll failed: ... Connection refused" each poll,
      and the program keeps running instead of crashing. Restart the
      server in window 1; the next poll should connect normally.

  TEST 6: Help text and required options
      python retriever.py --help    -> lists all options
      python retriever.py           -> error: --host is required

RESETTING BETWEEN TEST RUNS
  To start the tests again from scratch, delete:
      retrieved.txt
      the retrieved_files folder
      data_c.csv and data_d.csv from ftp_root (if you created them)
  Then remove data_d.csv from expected.txt.


TROUBLESHOOTING
---------------
  "Connection refused"
      The FTP server is not running, or the host/port is wrong.

  "530 Login incorrect" (or similar 530 message)
      Wrong username or password.

  "550 ..." when changing directory
      The --remote-dir folder does not exist on the server, or you do
      not have permission to open it.

  A file never downloads, even though it is on the server
      Check that its name in expected.txt matches the server exactly,
      including upper/lower case and extension.
      Check that it is not already listed in retrieved.txt.

  WARNING: expected list 'expected.txt' not found
      Run the program from the folder containing expected.txt, or give
      its location with --expected.

  "error: the following arguments are required: --host"
      You ran the program without --host. This also happens if you run
      the file inside Spyder with F5; run it from a terminal instead.

  A file needs to be downloaded again
      Delete its line from retrieved.txt. It will be fetched at the
      next poll.


KNOWN LIMITATIONS
-----------------
  - Files are tracked by NAME only. If a file is replaced on the server
    under the same name, it will not be downloaded again (unless you
    remove it from retrieved.txt).
  - If a file is still being uploaded to the server when a poll
    happens, a partial copy could be downloaded.
  - Only one remote directory is watched; subfolders are not searched.
  - Plain FTP sends usernames and passwords unencrypted. For sensitive
    data, a secure protocol such as SFTP or FTPS should be used.
