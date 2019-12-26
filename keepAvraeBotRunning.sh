#!/bin/bash
#Scripts to start services if not running

ps -ef | grep dbot |grep -v grep > /dev/null  #run with rekaj_dbot.py instead of dbot.py to test
if [ $? != 0 ]
then
	   #what does start do?  Do we need ...test start > /dev/null ?
	   sudo python3 dbot.py test > /dev/null &  #run with rekaj_dbot.py instead of dbot.py to test
	   disown
fi