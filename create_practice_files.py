# -*- coding: utf-8 -*-
"""
Created on Wed Sep 30 13:34:33 2026

@author: sabri
"""

#%% create practice files
import os

# Navigate to the project folder to run this file.

print("Working directory:", os.getcwd())

# ftp_root plays the part of the external directory on the FTP server.
os.makedirs("ftp_root", exist_ok=True)
for name in ["data_a.csv", "data_b.csv", "unrelated.txt"]:
    with open(os.path.join("ftp_root", name), "w") as f:
        f.write("id,value\n1,100\n")

# The expected list. data_c.csv is expected but hasn't "arrived" yet,
# and unrelated.txt is on the server but NOT expected.
with open("expected.txt", "w") as f:
    f.write("# Files we expect to receive\n")
    f.write("data_a.csv\ndata_b.csv\ndata_c.csv\n")

print("Server files:", sorted(os.listdir("ftp_root")))
print(open("expected.txt").read())