# The Last Sip

An original 22-second coffee-spill film and a matching editable Three.js scene. A porcelain cup tips on a walnut table; simulated coffee leaves the cup, spreads on the tabletop, runs over the front edge, and lands on an oak floor. The camera follows it through a fully modelled warm interior.

## Deliverables

- `public/film/last-sip-1080p.mp4`: finished 1920 × 1080 H.264 film, 24 fps, 528 frames, 22 seconds, original stereo foley. No titles, interface, branding or watermark in the film.
- `public/film/original-foley.wav`: separate original sound effects for editing.
- `public/film/delivery.json`: encoding properties, frame count, decode validation and SHA-256.
- `public/assets/`: original geometry, textures, exact cup transforms and baked liquid.
- GitHub Actions `render-cache` artifact: editable Blender master and full simulation cache.

The MP4 is the **offline Blender Cycles render**. The web app is a **Three.js reconstruction of the same evaluated geometry and liquid cache**, not a video plane pretending to be a simulation. Its real-time lighting approximates the offline path-traced lighting. The browser-capture script also exports the Three.js renderer itself to a separate MP4.

## Play and explore

Requires Node.js 20 or newer. No package installation is needed; Three.js 0.180.0 is vendored with its upstream MIT license.

```sh
npm start
```

Open the printed local address. Watch or download the film, or switch to the interactive scene. Seek on the timeline or use orbit mode to inspect geometry. No external asset host is required.

## Rebuild

Requires Blender 4.3.2, Python with NumPy and Pillow, and FFmpeg.

```sh
blender -b -t 4 --python tools/build_scene.py -- --mode build --resolution 160
blender -b -t 4 --python tools/build_scene.py -- --mode bake
blender -b -t 4 --python tools/build_scene.py -- --mode export
python tools/validate_cache.py
blender -b -t 4 --python tools/build_scene.py -- --mode render --start 0 --end 528 --width 1920 --samples 40
python tools/assemble.py
npm test
```

Frame ranges are `[start,end)`. The Actions renderer splits them into independent jobs and assembles only after all 528 frames exist. Cache paths are relocated automatically when the project moves to another machine.

## Physics and artistic choices

Coffee is an actual Mantaflow FLIP simulation: initial volume, moving cup collision mesh, gravity, table and floor collision meshes. No expanding puddle substitute or loop of animated droplets is used. All 288 liquid frames are baked and replayed deterministically. Quarter-speed physics makes the spill slow motion. The first four and last six seconds hold the corresponding liquid state while the camera moves.

The cup tipping is art-directed keyframe animation, not a rigid-body solve or two-way coupled solid/fluid dynamics. Geometry, procedural textures and synthesized foley are original to this project. The offline film is display-referred AgX with Rec.709 delivery metadata; it is not an ACES EXR package or a DCP. Studio acceptance depends on the production's own visual review and delivery specifications.

## Validation

`npm test` checks camera and timeline invariants. `python tools/validate_cache.py` checks every liquid buffer and confirms floor impact. Assembly checks native resolution, frame count, duration and frame rate, then decodes the entire MP4 with FFmpeg.

## Rights and provenance

No stock footage, purchased models, external music or generated human likenesses are used. Original scene, textures, animation and foley were created for this project. Third-party software retains its applicable license: Three.js MIT, Blender GPL, and FFmpeg/codecs under their respective licenses. Rendered creative assets are distinct from those software licenses.
