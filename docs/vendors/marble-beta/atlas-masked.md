# atlasMasked

POST /api/v2/tasks:atlasMasked

Submit the atlasMasked task



```sh
curl --request POST \
  --url 'https://api.atlas-beta.worldlabs.ai/api/v2/tasks:atlasMasked?wait=true' \
  --header "WLT-Api-Key: $WLT_API_KEY" \
  --header 'Idempotency-Key: request-001' \
  --header 'Content-Type: application/json' \
  --data '{
  "contextFrames": [
    {
      "imageAsset": {
        "assetId": "asset_01jexample000000000000000"
      },
      "maskAsset": {
        "assetId": "asset_01jexample000000000000000"
      },
      "camera": {
        "extrinsics": {
          "position": [
            1,
            1,
            1
          ],
          "quaternion": [
            1,
            1,
            1,
            1
          ],
          "coordinateSystem": "rub"
        },
        "intrinsics": {
          "fx": 1,
          "fy": 1,
          "cx": 1,
          "cy": 1,
          "width": 1280,
          "height": 720
        }
      }
    }
  ],
  "targetCameras": [
    {
      "extrinsics": {
        "position": [
          1,
          1,
          1
        ],
        "quaternion": [
          1,
          1,
          1,
          1
        ],
        "coordinateSystem": "rub"
      },
      "intrinsics": {
        "fx": 1,
        "fy": 1,
        "cx": 1,
        "cy": 1,
        "width": 1280,
        "height": 720
      }
    }
  ],
  "enhancePrompt": true,
  "returnDepth": false
}'
```


## Response

```json
{
  "id": "op_01jexample000000000000000000",
  "ownerId": "acct_01jexample00000000000000000",
  "metadata": null,
  "done": false,
  "error": null,
  "expiresAtSecs": 1789415864,
  "createdAtSecs": 1789412264,
  "response": null,
  "name": "accounts/acct_01jexample00000000000000000/projects/project_example/operations/op_01jexample000000000000000000"
}
```



## Completed response

```json
{
  "id": "op_01jexample000000000000000000",
  "ownerId": "acct_01jexample00000000000000000",
  "metadata": null,
  "done": true,
  "error": null,
  "expiresAtSecs": 1789415864,
  "createdAtSecs": 1789412264,
  "response": {
    "frames": [
      {
        "imageAsset": {
          "assetId": "asset_01jexample000000000000000",
          "url": "https://example.com/imageAsset.png"
        },
        "maskAsset": {
          "assetId": "asset_01jexample000000000000000",
          "url": "https://example.com/maskAsset.png"
        },
        "camera": {
          "extrinsics": {
            "position": [
              1,
              1,
              1
            ],
            "quaternion": [
              1,
              1,
              1,
              1
            ],
            "coordinateSystem": "rub"
          },
          "intrinsics": {
            "fx": 1,
            "fy": 1,
            "cx": 1,
            "cy": 1,
            "width": 1280,
            "height": 720
          }
        },
        "depth": {
          "confidenceAsset": {
            "assetId": "asset_01jexample000000000000000",
            "url": "https://example.com/confidenceAsset.png"
          },
          "logDepthAsset": {
            "assetId": "asset_01jexample000000000000000",
            "url": "https://example.com/logDepthAsset.exr"
          },
          "zMin": 1,
          "zMax": 1
        }
      }
    ],
    "promptUsed": "A cinematic world with clear depth, coherent geometry, and no people",
    "requestId": "string"
  },
  "name": "accounts/acct_01jexample00000000000000000/projects/project_example/operations/op_01jexample000000000000000000"
}
```



## OpenAPI specification

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Marble 2 Developer API",
    "summary": "External Developer API for Marble 2.",
    "description": "Developer API routes authenticate with a project API key and operate on that key's account and project.",
    "version": "2.0.0"
  },
  "paths": {
    "/api/v2/tasks:atlasMasked": {
      "post": {
        "tags": [
          "tasks"
        ],
        "summary": "Submit the atlasMasked task",
        "operationId": "submit_atlasMasked_api_v2_tasks_atlasMasked_post",
        "parameters": [
          {
            "name": "wait",
            "in": "query",
            "required": false,
            "schema": {
              "type": "boolean",
              "description": "Block for the operation to finish before returning, up to the server wait cap. Returns the Operation either way — done with a response if it finished in time, otherwise still running.",
              "default": false,
              "title": "Wait"
            },
            "description": "Block for the operation to finish before returning, up to the server wait cap. Returns the Operation either way — done with a response if it finished in time, otherwise still running."
          },
          {
            "name": "Idempotency-Key",
            "in": "header",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string",
                  "maxLength": 128
                },
                {
                  "type": "null"
                }
              ],
              "description": "Optional idempotency key.",
              "title": "Idempotency-Key"
            },
            "description": "Optional idempotency key."
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/AtlasMaskedRequest"
              }
            }
          }
        },
        "responses": {
          "201": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/AtlasMaskedResponseOperation"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        },
        "x-wlt-audience": "BETA",
        "x-marble-authorization": {
          "permission": "task.create",
          "additionalPermissions": [
            "operation.read"
          ]
        }
      }
    }
  },
  "components": {
    "schemas": {
      "AtlasMaskedRequest": {
        "properties": {
          "webhookUrl": {
            "anyOf": [
              {
                "type": "string",
                "maxLength": 2048
              },
              {
                "type": "null"
              }
            ],
            "title": "Webhookurl",
            "description": "Where Marble POSTs one signed task.succeeded or task.failed event when this operation finishes; retried for 24 hours. Verify the signature with the public keys at /.well-known/webhooks/jwks.json. Cannot be combined with ?wait=true. https on port 443 only, no IP literals. Developer API only."
          },
          "purgeContentOnOperationCompletion": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "title": "Purgecontentonoperationcompletion",
            "description": "Purge this operation's outputs and the transient uploads it consumed one hour after it finishes. Omitted, the account's setting applies; true raises it for this operation; false is refused when the account already purges. Uploads in the library are never purged by an operation."
          },
          "contextFrames": {
            "items": {
              "$ref": "#/components/schemas/PosedRGBAAsset"
            },
            "type": "array",
            "minItems": 1,
            "title": "Contextframes",
            "description": "The views to complete, in output order: each an image, its alpha mask, and its camera. The mask is an 8-bit grayscale PNG on the image grid where 1 is kept -- those pixels are the observed image -- and 0 is what the model fills in. Each view is completed at its targetCameras entry of the same index."
          },
          "targetCameras": {
            "items": {
              "$ref": "#/components/schemas/PinholeCamera"
            },
            "type": "array",
            "minItems": 1,
            "title": "Targetcameras",
            "description": "Pinhole cameras for the views to generate, one per context frame in the same order. Warning: the partial checkpoints condition target i on contextFrames[i]'s masked view and were trained with one context view per target, rendered from the target's own viewpoint. A count that differs from contextFrames, or a target off its frame's camera, is accepted but runs outside the training distribution and may generate degraded views."
          },
          "prompt": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Prompt",
            "description": "The edit to make. With enhancePrompt on (the default), write an instruction that names what to add, remove, replace, or restyle and where, such as 'replace the yellow car with a stone fountain in the middle of the courtyard'. The enhancer reads it with the original context images but not the masks. Without a prompt it describes the images as they are, which tends to restore masked objects, so state removals explicitly. With enhancePrompt false the model receives the text unchanged as a caption of the finished image, so describe the whole finished scene instead."
          },
          "enhancePrompt": {
            "type": "boolean",
            "title": "Enhanceprompt",
            "description": "Rewrite the prompt before inference: the edit instruction and the context images become a detailed description of the finished scene, returned as promptUsed. Set false to send the prompt exactly as given.",
            "default": true
          },
          "returnDepth": {
            "type": "boolean",
            "title": "Returndepth",
            "description": "Return the completed frames as posed RGBD: they are reconstructed together so the depth lands in the request's own camera frame and scale, and every entry in `frames` then carries a `depth` buffer. Needs at least two targetCameras. Limitation: the depth scale is recovered from the frames' camera centres, so views that share one centre (a pure-rotation rig) come back with a 0.0 or NaN scale and a success status.",
            "default": false
          },
          "modelParameters": {
            "$ref": "#/components/schemas/AtlasMaskedModelParameters",
            "description": "Model-specific parameters for atlasMasked."
          }
        },
        "type": "object",
        "required": [
          "contextFrames",
          "targetCameras"
        ],
        "title": "AtlasMaskedRequest",
        "description": "Body of ``POST /api/v2/tasks:atlasMasked``."
      },
      "AtlasMaskedResponseOperation": {
        "properties": {
          "id": {
            "type": "string",
            "title": "Id",
            "description": "Short operation id used in ``/operations/{operation}`` paths."
          },
          "ownerId": {
            "type": "string",
            "title": "Ownerid",
            "description": "Account that owns the operation."
          },
          "metadata": {
            "anyOf": [
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "title": "Metadata",
            "description": "Task information and optional progress details. Use ``metadata.task`` to interpret a generic operation response, and use ``done`` to determine completion."
          },
          "done": {
            "type": "boolean",
            "title": "Done",
            "description": "Whether the operation is terminal. When true, a non-null ``error`` indicates failure; otherwise the operation succeeded."
          },
          "error": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/OperationError"
              },
              {
                "type": "null"
              }
            ],
            "description": "Failure details when ``done`` is true and the task failed; null while running and after success."
          },
          "expiresAtSecs": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Expiresatsecs",
            "description": "Task execution deadline as Unix seconds, when one is exposed. This is not an asset URL expiration."
          },
          "createdAtSecs": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Createdatsecs",
            "description": "Unix seconds when the operation was accepted."
          },
          "response": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/AtlasMaskedResponse"
              },
              {
                "type": "null"
              }
            ],
            "description": "``AtlasMaskedResponse`` result when ``done`` is true and the task succeeded; null while running and after failure."
          },
          "name": {
            "type": "string",
            "title": "Name",
            "description": "Full resource name for the operation.\n\nFor project operations:\n``accounts/{account}/projects/{project}/operations/{operation}``.\nOperation paths accept the short ``id``.",
            "readOnly": true
          }
        },
        "type": "object",
        "required": [
          "id",
          "ownerId",
          "done",
          "name"
        ],
        "title": "AtlasMaskedResponseOperation",
        "description": "Long-running operation whose successful terminal ``response`` has type ``AtlasMaskedResponse``. This is the common Operation envelope with a task-specific response type, not a separate operation resource."
      },
      "HTTPValidationError": {
        "properties": {
          "detail": {
            "items": {
              "$ref": "#/components/schemas/ValidationError"
            },
            "type": "array",
            "title": "Detail"
          }
        },
        "type": "object",
        "title": "HTTPValidationError"
      },
      "PosedRGBAAsset": {
        "properties": {
          "imageAsset": {
            "$ref": "#/components/schemas/TaskAsset",
            "description": "Source image as a URL or inline asset."
          },
          "maskAsset": {
            "$ref": "#/components/schemas/TaskAsset",
            "description": "Alpha mask as a URL or inline asset: an 8-bit grayscale PNG on the image grid whose pixel value / 255 is the alpha in [0, 1] (1 = kept, 0 = excluded)."
          },
          "camera": {
            "$ref": "#/components/schemas/PinholeCamera",
            "description": "Camera-to-world pose and intrinsics."
          },
          "depth": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/LogDepthBufferAsset"
              },
              {
                "$ref": "#/components/schemas/LinearDepthBufferAsset"
              },
              {
                "type": "null"
              }
            ],
            "title": "Depth",
            "description": "Optional depth buffer, as an inverted log-depth PNG (logDepthAsset) or a linear-depth EXR (depthAsset)."
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "imageAsset",
          "maskAsset",
          "camera"
        ],
        "title": "PosedRGBAAsset",
        "description": "A posed frame carrying both its RGB image and its alpha mask."
      },
      "PinholeCamera": {
        "properties": {
          "extrinsics": {
            "$ref": "#/components/schemas/CoordinateFrame"
          },
          "intrinsics": {
            "$ref": "#/components/schemas/PinholeCameraIntrinsics"
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "extrinsics",
          "intrinsics"
        ],
        "title": "PinholeCamera",
        "description": "A posed pinhole camera.\n\nThe axes convention of the pose is carried by\n``extrinsics.coordinate_system``."
      },
      "AtlasMaskedModelParameters": {
        "properties": {
          "seed": {
            "anyOf": [
              {
                "type": "integer",
                "minimum": 0
              },
              {
                "type": "null"
              }
            ],
            "title": "Seed",
            "description": "RNG seed forwarded to the servable when set.",
            "default": 42
          },
          "numSteps": {
            "anyOf": [
              {
                "type": "integer",
                "maximum": 100,
                "minimum": 1
              },
              {
                "type": "null"
              }
            ],
            "title": "Numsteps",
            "description": "Diffusion step count.",
            "default": 50
          }
        },
        "type": "object",
        "title": "AtlasMaskedModelParameters",
        "description": "Model-specific parameters forwarded to the atlasMasked servable."
      },
      "OperationError": {
        "properties": {
          "code": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Code",
            "description": "Numeric status code; conventionally a google.rpc.Code value."
          },
          "message": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Message",
            "description": "Developer-readable error message in English."
          },
          "details": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "type": "array",
            "title": "Details",
            "description": "Structured error details, matching google.rpc.Status.details."
          }
        },
        "type": "object",
        "title": "OperationError",
        "description": "Error payload set on a failed operation."
      },
      "AtlasMaskedResponse": {
        "properties": {
          "frames": {
            "anyOf": [
              {
                "items": {
                  "$ref": "#/components/schemas/PosedRGBAsset"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "title": "Frames",
            "description": "Generated frames (image + camera): one per target camera, in order. Every frame also carries a `depth` buffer when the request set returnDepth."
          },
          "promptUsed": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Promptused",
            "description": "Final prompt supplied to inference, if any."
          },
          "requestId": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Requestid",
            "description": "Meridian request id from servable runtime metadata."
          }
        },
        "type": "object",
        "title": "AtlasMaskedResponse",
        "description": "Public response projected into the completed Operation."
      },
      "ValidationError": {
        "properties": {
          "loc": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array",
            "title": "Location"
          },
          "msg": {
            "type": "string",
            "title": "Message"
          },
          "type": {
            "type": "string",
            "title": "Error Type"
          },
          "input": {
            "title": "Input"
          },
          "ctx": {
            "type": "object",
            "title": "Context"
          }
        },
        "type": "object",
        "required": [
          "loc",
          "msg",
          "type"
        ],
        "title": "ValidationError"
      },
      "TaskAsset": {
        "properties": {
          "assetId": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Assetid",
            "description": "Account-owned asset id, e.g. `asset_...`."
          },
          "base64": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Base64",
            "description": "Base64-encoded media bytes, with or without a data URL prefix. Decoded size must be less than 10 MiB. A task response carries inline bytes only when it is returned from the submission; the stored operation names the same output by `assetId` and `url`."
          },
          "url": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Url",
            "description": "Public HTTP(S) URL containing the media. On a task response this is a read URL for `assetId` and it expires; mint a fresh one with `assets/{asset}:createReadUrl`."
          }
        },
        "additionalProperties": false,
        "type": "object",
        "title": "TaskAsset",
        "description": "Media named by asset id, inline base64, or public URL.\n\nA task response names each output by id and url together: the url expires,\nthe id does not. The pair is accepted as input as well, so a response can\nbe handed straight back to the next task; the id names the media and the\nurl is ignored. Inline base64 stands alone. A response returns it only\nwhen a task is answered at submission; the stored operation names the\nsame output by id and url."
      },
      "LogDepthBufferAsset": {
        "properties": {
          "confidenceAsset": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/TaskAsset"
              },
              {
                "type": "null"
              }
            ],
            "description": "Optional 8-bit grayscale PNG on the depth grid whose pixel value / 255 is the per-pixel depth confidence in [0, 1], as a URL or inline asset."
          },
          "logDepthAsset": {
            "$ref": "#/components/schemas/TaskAsset",
            "description": "Inverted log-depth grayscale PNG, as a URL or inline asset."
          },
          "zMin": {
            "type": "number",
            "title": "Zmin",
            "description": "Linear depth in world units encoded as white (1.0)."
          },
          "zMax": {
            "type": "number",
            "title": "Zmax",
            "description": "Linear depth in world units encoded as black (>0)."
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "logDepthAsset",
          "zMin",
          "zMax"
        ],
        "title": "LogDepthBufferAsset",
        "description": "Inverted log-depth PNG (URL or inline asset) plus its decode range."
      },
      "LinearDepthBufferAsset": {
        "properties": {
          "confidenceAsset": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/TaskAsset"
              },
              {
                "type": "null"
              }
            ],
            "description": "Optional 8-bit grayscale PNG on the depth grid whose pixel value / 255 is the per-pixel depth confidence in [0, 1], as a URL or inline asset."
          },
          "depthAsset": {
            "$ref": "#/components/schemas/TaskAsset",
            "description": "EXR of linear depth in world units, as a URL or inline asset."
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "depthAsset"
        ],
        "title": "LinearDepthBufferAsset",
        "description": "Linear-depth EXR (URL or inline asset)."
      },
      "CoordinateFrame": {
        "properties": {
          "position": {
            "prefixItems": [
              {
                "type": "number"
              },
              {
                "type": "number"
              },
              {
                "type": "number"
              }
            ],
            "type": "array",
            "maxItems": 3,
            "minItems": 3,
            "title": "Position",
            "items": {
              "type": "number"
            }
          },
          "quaternion": {
            "prefixItems": [
              {
                "type": "number"
              },
              {
                "type": "number"
              },
              {
                "type": "number"
              },
              {
                "type": "number"
              }
            ],
            "type": "array",
            "maxItems": 4,
            "minItems": 4,
            "title": "Quaternion",
            "items": {
              "type": "number"
            }
          },
          "coordinateSystem": {
            "type": "string",
            "enum": [
              "rub",
              "rdf"
            ],
            "title": "Coordinatesystem",
            "default": "rub"
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "position",
          "quaternion"
        ],
        "title": "CoordinateFrame",
        "description": "Pose represented by a position and an XYZW quaternion.\n\n``coordinate_system`` names the axes convention the pose is expressed in:\n``rub`` (right-up-back, the OpenGL/Three.js convention) or ``rdf``\n(right-down-forward, the OpenCV convention). Both the ``coordinateSystem``\n(camelCase) and ``coordinate_system`` spellings are accepted."
      },
      "PinholeCameraIntrinsics": {
        "properties": {
          "fx": {
            "type": "number",
            "title": "Fx"
          },
          "fy": {
            "type": "number",
            "title": "Fy"
          },
          "cx": {
            "type": "number",
            "title": "Cx"
          },
          "cy": {
            "type": "number",
            "title": "Cy"
          },
          "width": {
            "type": "integer",
            "title": "Width"
          },
          "height": {
            "type": "integer",
            "title": "Height"
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "fx",
          "fy",
          "cx",
          "cy",
          "width",
          "height"
        ],
        "title": "PinholeCameraIntrinsics",
        "description": "Pinhole camera intrinsics in pixel coordinates (not normalized).\n\nPixel coordinates have their origin (0, 0) at the top-left corner of the\nimage, +x right and +y down, so ``cx``/``cy`` measure from the top-left.\n``width`` and ``height`` are the image size in pixels the intrinsics\nrefer to. This is independent of the pose's ``coordinate_system``."
      },
      "PosedRGBAsset": {
        "properties": {
          "imageAsset": {
            "$ref": "#/components/schemas/TaskAsset",
            "description": "Source image as a URL or inline asset."
          },
          "maskAsset": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/TaskAsset"
              },
              {
                "type": "null"
              }
            ],
            "description": "Optional alpha mask as a URL or inline asset: an 8-bit grayscale PNG on the image grid whose pixel value / 255 is the alpha in [0, 1] (1 = kept, 0 = excluded). Null when the frame carries no mask."
          },
          "camera": {
            "$ref": "#/components/schemas/PinholeCamera",
            "description": "Camera-to-world pose and intrinsics."
          },
          "depth": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/LogDepthBufferAsset"
              },
              {
                "$ref": "#/components/schemas/LinearDepthBufferAsset"
              },
              {
                "type": "null"
              }
            ],
            "title": "Depth",
            "description": "Optional depth buffer, as an inverted log-depth PNG (logDepthAsset) or a linear-depth EXR (depthAsset)."
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "imageAsset",
          "camera"
        ],
        "title": "PosedRGBAsset",
        "description": "A posed RGB frame: image plus its known camera."
      }
    },
    "securitySchemes": {
      "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "WLT-Api-Key"
      }
    }
  },
  "security": [
    {
      "ApiKeyAuth": []
    }
  ],
  "servers": [
    {
      "url": "https://api.atlas-beta.worldlabs.ai"
    }
  ]
}
```

