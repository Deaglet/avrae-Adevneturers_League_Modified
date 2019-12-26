#!/bin/bash
#Scripts to start services if not running

ps -ef | grep rekaj_dbot |grep -v grep > /dev/null
if [ $? != 0 ]
then
       sudo python3 rekaj_dbot.py test start > /dev/null 
fi