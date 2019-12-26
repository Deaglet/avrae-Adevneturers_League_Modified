#!/bin/bash
#Scripts to start services if not running

ps -ef | grep dbot |grep -v grep > /dev/null
if [ $? != 0 ]
then
       <locationOfdbot.py> start > /dev/null
fi