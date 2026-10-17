> ## Documentation Index
> Fetch the complete documentation index at: https://docs.worldlabs.ai/llms.txt
> Use this file to discover all available pages before exploring further.

> Specify more details by combining multiple images.

# Multi-image prompt tips

<iframe width="100%" height="400" src="https://www.youtube.com/embed/weTbkz5yioc" title="Multi-image Prompt Tips" frameBorder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen />

# Creating worlds with multiple images with direction control

In the <Icon icon="image" /> 2D input mode of omnibox, drag in or upload up to 4 images.
Click on the text overlay on image thumbnails to change its direction, and choose one from "Front", "Back", "Left", "Right".
For this mode, images without overlap allow the marble models to creatively fill in the spaces between views.
When you are done specifying the direction of each image, click on <Icon icon="brush" /> Create to generate the world.
For image file specifications, see [Prompt guidelines →](/marble/create/prompt-guides)

* Direction control is great for connecting different environments creatively.

# Creating worlds with multiple images with Auto Layout

In the <Icon icon="image" /> 2D input mode of omnibox, drag in or upload up to 8 images.
Toggle "Auto Layout" switch to on so the world model automatically determines the relative positioning of these images.
In this mode, all uploaded images need to share the same aspect ratio and resolution, and should be images from the same space.
Currently images captured in close proximity of each other but covering different viewing directions, and with some overlap between images, work the best.
Click on <Icon icon="brush" /> Create to generate the world.

* Auto layout is great for quick reconstruction of existing spaces.

<Note>
  Auto Layout works on standard flat images and reconstructs a single space. It does not accept 360° panoramas, and you can upload only one panorama per world (a panorama can't be combined with other images or a video). To build a larger multi-room space such as a whole house, generate a separate world from each panorama or image set (one per room or vantage point), then combine them with [Studio Compose](/marble/create/studio-tools/compose). See the [Panorama prompt guide](/marble/create/prompt-guides/pano-prompt) for single-panorama capture.
</Note>

## What Auto Layout can reconstruct

Auto Layout rebuilds one coherent space from what your images actually show. Parts of the scene the cameras never see, such as behind closed doors, around solid walls, or up a staircase, are generated plausibly to keep the world explorable, so they won't match a real floor plan of those hidden areas.

For a full multi-room house or building:

* Capture open-plan areas where rooms share sightlines, and shoot from a few overlapping vantage points so most of the space stays in view. A [360 panorama](/marble/create/prompt-guides/pano-prompt) gives the most accurate single-space layout.
* To connect genuinely separate, walled-off rooms into one walkable building, generate each room on its own and arrange them with [Studio Compose](/marble/create/studio-tools/compose).

## Troubleshooting multi-image issues

### "Auto Layout not working properly"

* **Verify aspect ratios**: Ensure all images have exactly the same width-to-height ratio
* **Check for overlap**: Include visual elements that appear in multiple images
* **Improve image quality**: Use sharp, well-lit images with clear details
* **Check lighting consistency**: Try to match lighting conditions and color temperatures
* **Use images from same location**: Confirm all images are truly of the same space

Multi-image prompting allows you to build more complex, interesting worlds than single images alone.
The key is thoughtful planning of how your images relate spatially and visually to create cohesive, explorable environments.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.