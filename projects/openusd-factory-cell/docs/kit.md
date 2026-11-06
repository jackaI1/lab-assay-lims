# Opening the cell in Omniverse Kit

I keep generation separate from the viewer. The command line creates ordinary USD files, and the extension opens those same files in Kit. It does not install another USD runtime inside Kit.

## Generate a bundle first

From the repository root, with the Python environment in the README activated:

```sh
factory-cell generate --output build/my-cell --fixture clamp --seconds 8 --fps 24
factory-cell validate build/my-cell/cell.usda
```

The output directory must be new. Keep its `assets/`, `layout.usda` and `motion.usda` files with `cell.usda`.

## Enable the extension

I wrote this adapter against the Kit 107-style `omni.ext`, `omni.ui`, `omni.usd` and `omni.timeline` APIs. Use a Kit application that includes a USD viewport, such as a locally installed USD Composer or an editor built with the Kit App Template. Kit requires a supported NVIDIA GPU and host system; the Python generator does not.

1. Save any changes in the currently open scene.
2. In **Window > Extensions**, open the extension search path settings and add the absolute path to this repository's `exts` directory. This is the parent of `jack.factory.cell`.
3. Search for **Factory Cell** and enable it. The extension opens a small window.
4. Paste the full local path to `build/my-cell/cell.usda`, then click **Load stage**. The extension validates the file before replacing the current scene and shows a PASS or FAIL report.
5. Select `/World/Camera` as the viewport camera, or frame `/World/Cell` with the viewport controls.
6. Click **Start**. It validates again, resets time to the beginning and plays the cycle. **Stop** stops playback started by this extension. **Validate** checks the current cell without editing it.

For a Kit application started from a terminal, the equivalent extension flags are:

```sh
/path/to/kit /path/to/editor.kit --ext-folder /absolute/path/to/openusd-factory-cell/exts --enable jack.factory.cell
```

The extension does not replace a stage on startup. It supports local files, not Nucleus URLs. If I switch to another scene, the controls refuse to play or stop that scene. Disabling the extension cancels a pending load, stops playback it started, and destroys its window. It keeps the loaded scene open so I can continue editing.

## What I tested, and what still needs a GPU

The automated adapter tests read `extension.toml`, import its declared module and run its actual startup, load, start, stop, validation and shutdown methods. They use real USD stages; small stand-ins supply the unavailable Kit window, context and timeline interfaces. They also test cancellation of a pending load and destruction of the window.

I have not run a native Kit viewport in this repository's macOS test environment. The host harness proves the Python integration logic, not GPU rendering or compatibility with every Kit release. For a native smoke test, follow the steps above, confirm the green part reaches the fixture and outfeed, then open another scene and confirm the extension refuses to control it. Disable the extension during a load and confirm the window closes without an unhandled task error.

I used NVIDIA's [extension manifest reference](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/guide/extensions_advanced.html), [USD context API](https://docs.omniverse.nvidia.com/kit/docs/omni.usd/latest/omni.usd/omni.usd.UsdContext.html) and [timeline API](https://docs.omniverse.nvidia.com/kit/docs/omni.timeline/latest/omni.timeline/omni.timeline.ITimeline.html) for the adapter. The core follows OpenUSD's [layer and animation tutorial](https://openusd.org/release/tut_xforms.html) and [reference tutorial](https://openusd.org/release/tut_referencing_layers.html).
