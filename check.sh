#!/bin/bash
ret=$(ps aux | grep "/usr/bin/python3 support_planner.py"  | wc -l)
if [[ "$ret" -eq 0 || "$ret" -eq 1 ]];
then {
  echo $(date +%Y-%m-%d-%H-%M%S) + "Start support-team-planner" >> support-team-planner.log #output text
  sleep 1  #delay
  /bin/bash run.sh > support-team-planner.log #command for run program
  exit 1
}
else {
  echo $(date +%Y-%m-%d-%H-%M%S) + "EXIT. support-team-planner already running!" >> support-team-planner.log
  exit 1
}
fi;
