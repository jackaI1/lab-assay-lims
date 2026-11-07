# robot-cluster-scheduler

I built a simulator for a group of robots and shared lab equipment to learn how the underlying idea works. This is a learning project.

I use example batches and simulated robots and equipment to compare schedules.

## Try it

Install Python 3.9 or newer, then run:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install '.[test]'
python -m robot_scheduler --seed 42 --batches 12
```

The command prints JSON for first-in-first-out (FIFO) and earliest due date. Each result includes the finish time, throughput per hour, resource utilization, lateness in seconds and a record of each step. Change the seed to explore another set of delays and faults, or change the batch count to increase the workload. For the default example, seed 42 produces about 17.9 and 18.4 batches per hour respectively. These results depend on the workload and assumptions, so they are not predictions for a real facility.

## How it works

A batch has an arrival time, due time and ordered steps. Each step names its duration and required resources. FIFO chooses waiting steps in the order they enter the queue; earliest due date gives priority to the batch due soonest. Both rules skip a blocked step when another can run with the resources available.

The dispatcher reserves all resources a step needs together. This avoids deadlock, where steps each hold a resource while waiting for another. A robot fault extends the current step by a repair delay while its resources remain occupied. A separate seeded random stream per batch makes runs repeatable and makes comparisons less dependent on the order batches are dispatched.

To model another workload, import `Batch`, `Step`, and `simulate` from `robot_scheduler.simulation` and supply batches and resource capacities. Times are seconds. The model assumes each step needs at most one unit of each named resource; it does not model travel, maintenance schedules, or different robot capabilities. Lateness is the positive part of finish time minus due time, and utilization is occupied resource time divided by capacity and elapsed time from time zero to the last completion.

## Tests and limits

There are 1 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `robot-cluster-scheduler-ci.yml`. Their commands use this folder and their triggers use its paths.
