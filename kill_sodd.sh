ps -ef | grep "python sodd.py" | grep -v grep | awk '{print $2}' | xargs kill
