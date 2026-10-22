# Cameras and posed images

Bring calibrated images into Marble without breaking their geometry.

A posed image is an image plus the camera that captured or rendered it. Marble
uses that pairing to understand which ray produced each pixel, relate views in
one 3D coordinate frame, and keep generated RGB and depth geometrically
aligned.

Use this guide when you already have calibrated renders, COLMAP/OpenCV output,
or cameras from a 3D engine. If you only have images, start with
[Images to posed RGBD](/docs/images-to-posed-images) and let Marble estimate
the cameras.

## The camera model

Marble 2 uses a pinhole camera with two parts:

- **Intrinsics** describe the lens and image grid: `fx`, `fy`, `cx`,
  `cy`, `width`, and `height`.
- **Extrinsics** describe the camera-to-world pose: a world-space `position`,
  an XYZW `quaternion`, and a `coordinateSystem`.

```json
{
  "imageAsset": { "assetId": "assets/your-image" },
  "camera": {
    "intrinsics": {
      "fx": 1200,
      "fy": 1200,
      "cx": 960,
      "cy": 540,
      "width": 1920,
      "height": 1080
    },
    "extrinsics": {
      "position": [0, 1.6, 4],
      "quaternion": [0, 0, 0, 1],
      "coordinateSystem": "rdf"
    }
  }
}
```

The intrinsics are in pixels, not normalized coordinates. Pixel `(0, 0)` is
the image's top-left corner, +x points right, and +y points down. `width` and
`height` name the pixel grid those intrinsics describe.

The pose is **camera-to-world**, not a view or world-to-camera transform. If
your tool exports world-to-camera matrices, invert each rigid transform before
converting its rotation to a quaternion. Quaternions use XYZW order and should
be unit length.

## RUB and RDF coordinates

`coordinateSystem` tells Marble which local camera axes your pose uses.

| Value   | Camera axes                                     | Common sources                        |
| ------- | ----------------------------------------------- | ------------------------------------- |
| `"rub"` | right, up, back; the camera looks along -Z      | OpenGL, Three.js, Blender camera axes |
| `"rdf"` | right, down, forward; the camera looks along +Z | OpenCV and many calibration tools     |

Use the convention your camera-to-world pose was calculated in. Do not change
only the string to convert a pose: the orientation basis must be converted too.
Within one request, every position and orientation must describe the same world
frame and use the same distance unit.

The world frame matters too. For example, Blender is Z-up while Marble's RUB
world is Y-up, so a Blender export must convert the world-space pose even
though the camera's local axes are already RUB.

## Estimating an unposed camera

`images2PosedRGBD` takes images alone and estimates their cameras; a frame
that carries one is rejected rather than ignored. The output grid defaults to
1280 x 720; set `targetResolution` only when the result must fit a different
downstream raster:

```json
{
  "frames": [
    {
      "imageAsset": { "assetId": "assets/view-000" }
    }
  ],
  "canonicalizeToFirstFrame": false
}
```

The task always gravity-levels the reconstruction and selects confidence from
the available single-view or multi-view evidence.

## Resizing without changing the rays

An image and its camera are one geometric unit. Never resize or crop the pixels
while leaving the intrinsics unchanged.

For `images2PosedRGBD`, use the 1280 x 720 default or request another grid
with `targetResolution`, then use the returned image, depth, and camera
unchanged. The formulas below apply only when you own a plain resize with no
crop; they do not reproduce the task's scale-to-cover and center-crop
transform.

For a plain resize from `W × H` to `W' × H'`, set:

```text
sx = W' / W              sy = H' / H
fx' = sx * fx            fy' = sy * fy
cx' = sx * cx            cy' = sy * cy
width' = W'              height' = H'
```

If you then crop `x0` pixels from the left and `y0` from the top, also
shift the principal point:

```text
cx' = sx * cx - x0
cy' = sy * cy - y0
```

Apply the identical pixel transform to any mask, confidence image, or depth
buffer paired with the frame. A mask that is merely the same width and height
but came from a different crop is not aligned.

Marble's wire camera has no lens-distortion coefficients. Undistort or rectify
fisheye and distorted images before upload, then provide the intrinsics of the
rectified pixels.

## Scale and depth

Camera positions establish the rig's scale. If positions are measured in
metres, registered linear depth is in metres; if they use another consistent
unit, depth follows that unit.

Use translated views with a meaningful baseline when scale matters. A
pure-rotation sequence (multiple orientations sharing one camera center) does
not provide a baseline from which depth scale can be recovered.

Returned linear-depth EXRs are aligned to the returned camera and its declared
grid. Treat the camera, RGB, depth, and confidence output as one bundle rather
than mixing fields from different views or runs.

## Decode linear-depth EXR rows

Marble 2 camera intrinsics, RGB images, and confidence maps use top-left image
coordinates: row 0 is the top row. Three.js `EXRLoader` decodes EXR data in the
bottom-up row order used by its WebGL texture path. If CPU code reads the
returned `data` array to unproject points, draw a canvas preview, or compare
depth with RGB or confidence pixels, map a top-down y coordinate to
`height - 1 - y`.

With the downloaded EXR in an `ArrayBuffer` named `buffer`:

```ts
import { FloatType, RedFormat } from "three";
import { EXRLoader } from "three/examples/jsm/loaders/EXRLoader.js";

const decoded = new EXRLoader().setDataType(FloatType).setOutputFormat(RedFormat).parse(buffer);

function depthAt(x: number, yFromTop: number): number {
  const sourceY = decoded.height - 1 - yFromTop;
  return decoded.data[sourceY * decoded.width + x];
}
```

This conversion changes only how CPU code indexes the decoded array. It does
not require another API request or a rewritten EXR. `EXRLoader.load()` already
configures its Three.js texture for the decoded row order, so do not flip the
texture a second time.

A quick diagnostic is to draw the unprojected points with the camera frustum
and matching RGB image. If image features align only after reflecting depth
across the horizontal centerline, the decoded row order is wrong. In a
gravity-aligned scene with a visible floor, the floor should also stay below
the camera rather than reflect above it.

## Validation checklist

Before submitting your own posed images, verify:

1. Every pose is camera-to-world and every quaternion is XYZW.
2. `coordinateSystem` matches the pose's actual camera axes.
3. All cameras share one world frame and distance unit.
4. Every image is undistorted and paired with its own camera.
5. Intrinsics describe the uploaded image after its final resize and crop.
6. Masks and depth are pixel-aligned with the same final grid.
7. CPU-decoded depth is remapped out of the decoder's row order before matching image pixels.
8. Frame order is preserved across images, cameras, masks, and target cameras.
9. The task's exact resolution and view-count requirements are satisfied.

If geometry is vertically mirrored while the camera frustum is correct, check
the decoded EXR row order before changing the camera. If geometry is mirrored
left-to-right or behind the camera, inspect the pose direction and coordinate
convention. If geometry is correctly oriented but shifted or scaled
incorrectly, inspect the shared world frame, camera centers, and units.