#!/bin/bash
#Scripts to start services if not running

ps -ef | grep dbot |grep -v grep > /dev/null
if [ $? != 0 ]
then
       python3 dbot.py test 
fi