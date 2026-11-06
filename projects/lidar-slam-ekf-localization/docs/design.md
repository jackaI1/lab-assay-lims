# Coordinate conventions

Poses are `(x, y, yaw)` in metres and radians. A scan stores beam angle in the robot frame and range in metres. Grid arrays are indexed `[y, x]` with the origin in the centre. Log odds are clipped to prevent permanent saturation. Max-range returns update free space without adding an occupied endpoint.

The reference grid is built from 25 surveyed viewpoints, frozen and passed to the particle filter. The online grid uses EKF poses. The corrected grid uses nine graph keyframes and their scans; it is deliberately sparse. In the graph, the edge measurement from node i to j is j's pose in i's frame. ICP maps the final scan into the initial scan's frame. Gauss-Newton uses finite differences and fixes the first node. A loop candidate is supplied by the known end of the simulated lap, not discovered by place recognition.

The `results` files are generated and are not checked in. Benchmark errors compare coordinates directly because all methods start in the same frame. The final drift is absolute position error, not normalized by distance travelled. This is a simulation without dynamic obstacles, timing skew or realistic sensor occlusion, and the results do not establish performance on hardware.
