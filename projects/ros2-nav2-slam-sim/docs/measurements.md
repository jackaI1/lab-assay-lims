# Measurements and limits

The two wall cabinets make the room asymmetric. Loop candidates must be within 1 m with a chain of 20 scans and stricter coarse/fine match responses; this avoids confusing similar bench views. Each experiment first starts a fresh Gazebo world with a seeded laser noise generator and encoder wheel odometry. It drives six stations while slam_toolbox builds a 5 cm grid. The map saver writes the map received from SLAM; the floor geometry is never used to generate a navigation map. It stops all mapping processes and starts a fresh simulator with the saved map server, AMCL, and Nav2.

The second patrol includes a 1.2 m box centred on its first goal. The simulator inserts it through `/spawn_entity`, and the real laser observes it. The runner waits for `NavigateToPose` feedback to report `number_of_recoveries > 0` before deleting the box through `/delete_entity`. An abort, timeout, missing recovery, or skipped goal fails the experiment. This tests a blocked station becoming available again, rather than a permanently unreachable goal or a human-safe obstacle response.

Nav2's standard Humble recovery tree replans, clears costmaps, and can spin, wait and back up. A recovery count proves entry into recovery; it does not prove every recovery action ran. Goal completion is checked through action results, not proximity alone.

## Position

`libgazebo_ros_p3d` publishes the actual base-link pose at 30 Hz on `/ground_truth`. `libgazebo_ros_diff_drive` publishes encoder odometry separately. AMCL receives only the saved map, laser and odometry transforms. The logger interpolates ground-truth x, y and wrapped yaw around each AMCL timestamp. It rejects pairs spanning more than 0.3 s and estimates outside the recorded interval. The CSV retains both poses, Euclidean position error, and absolute wrapped heading error.

The report includes sample count, position RMSE, maximum position error, and heading RMSE over the whole patrol, including the blocked-goal period. These are update-weighted errors, so stationary waits contribute fewer samples than moving intervals. It does not remove startup errors or optimize a coordinate alignment. Both runs begin at the marked origin with a supplied initial pose. This measures tracking from a known start, not global relocalization after kidnapping. Seeds control Gazebo physics/sensor randomness; thread scheduling and AMCL's internal sampler can still vary results, so seeds do not promise bit-identical logs.

## Map

`map_accuracy` reads the actual PGM from map_saver. It checks the eight-by-eight-metre interior against the boxes used to build the world:

- Occupied precision: fraction of measured occupied cell centres within 12 cm of a true fixture boundary. This tolerates grid quantization and scan noise.
- Boundary recall: fraction of true interior-facing wall and bench boundary samples within 12 cm of a measured occupied cell. Unknown or missing boundaries count as misses.
- Known fraction: fraction of the interior classified free or occupied, so leaving most of a map unknown cannot pass.
- Known-cell accuracy: occupied/free agreement among known cells. This diagnostic is mostly free space, so it is reported alongside boundary measures rather than used alone.

The pass thresholds are precision above 85%, boundary recall above 70%, known area above 85%, position RMSE below 25 cm, heading RMSE below 0.2 rad, at least 30 paired AMCL samples, at least 50 observed scans per phase, and six successful patrol stations with an observed recovery. An aggregate reports the mean and worst accuracy across independent seeds. Bags use simulation timestamps, so replayed scans and transforms share the same clock. Raw bags, CSV and map artifacts let someone recalculate the results.

The floor is flat and the benches do not move. The lidar noise is only 5 mm Gaussian range noise. There is no wheel slip calibration, glass, crowded traffic or physical emergency stop. The simulation is useful for checking navigation wiring and regressions, but it is not a real-robot safety or accuracy claim.
