#!/bin/bash
#This script finds the bot and kills it.  In combination with keepAvraeBotRunning.sh should come back online after 60 to 120 seconds.

#What this does
# executes everything in $() then feeds to kill
# ps gives all processes, aux or -aux shows all processes for all users.
# grep finds processes that only contain '' 
# awk is a micro programming language.  Means run an awk command 
# awk '{print $<>}' means print certain column

# Here we want to take all processes for all users where name is "python3 dbot" and only output the 2nd column, the PID so we can kill it.


kill $(ps aux | grep 'python3 dbot' | awk '{print $2}')