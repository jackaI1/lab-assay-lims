# How I split the cell into editable files

I wanted to compare workholding options and change the cycle time without rebuilding the equipment. I chose a layered USD bundle, rather than one flattened file, because changes to motion should not change the machine geometry. A single file would be easier to send around, but it would lose those editable boundaries.

The generated `cell.usda` is the entry point. It composes `motion.usda` above `layout.usda`, so motion has priority. Layout references four asset files under `assets/`: conveyor, robot, fixture and part. All paths inside the bundle are relative. Moving the whole directory preserves the scene. Moving just the entry file does not.

The scene uses metres and Z as the up direction. `/World/Cell` holds the four equipment groups. The fixture asset contains a `fixture` variant set: `clamp` adds two jaws, and `nest` adds locating walls. The selected option is authored on the layout, leaving the reusable asset unchanged.

The robot is a simplified SCARA arm: two horizontal rotating links and a vertical tool slide. I solve the two-link inverse kinematics, meaning the joint angles needed to reach each target, and write a pose at every frame. The part travels along the conveyor, lifts to the fixture, waits, and returns to the outfeed. During transfer, the tool follows the part. Frame sampling approximates movement between frames. This is a layout and handoff review, with no contact solver, motor model or safety certification.

The generator accepts a fixture, cycle length in seconds and integer frame rate. It bounds the number of generated samples and rejects invalid inputs before writing anything. It writes a temporary sibling directory and publishes the bundle only after generation succeeds. An existing output directory is never replaced.

The validator checks the composed scene and its dependencies. It checks the required hierarchy, units, selected fixture, timing, finite sampled motion, expected handoff positions and robot tracking. The report is JSON, and failed validation gives the command a nonzero exit status. It checks this project's cell contract, rather than every possible USD scene or real machine clearance.

The extension loads the same Python core from `src/factory_cell/` that I package for the command line. Kit supplies its own `pxr` runtime. Only `factory_cell_kit` imports `omni.*`. A controller receives the stage context and timeline through its constructor; tests can use real USD files and small Kit boundary doubles. Loading is asynchronous, Start validates first, and controls refuse to affect another stage if the user changes scenes. Disabling the extension cancels its pending load and stops only playback it owns. It leaves the loaded stage available to the user.
