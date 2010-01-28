"""manual tests for scheduler"""

#import time
import scheduler

if __name__ == "__main__":
    sched = scheduler.Scheduler()

    #sched.add_task(ProcessTask(['echo', 'xx'], lock="xx"), 2)
    #sched.add_task(ProcessTask(['python', 'sample1.py', '5'], 3, lock="xx"))
#     time.sleep(2.5)
#     sched.add_task(ProcessTask(['python', 'sample1.py', '5'], 3))
#     sched.add_task(ProcessTask(['echo', 'xx']), 10)

    # test periodic
#    def print_hi():
#        print "hi"
#    sched.add_task(PeriodicTask(10, Task, print_hi))

#     # test group
#     t1 = ProcessTask(['python', 'sample1.py', '5'])
#     t2 = ProcessTask(['echo', 'xx'])
#     sched.add_task(GroupTask([t1,t2]))


    # test hang
    sched.add_task(scheduler.ProcessTask(['python', 'tests/hang.py', '5'], 3))

    sched.loop()

