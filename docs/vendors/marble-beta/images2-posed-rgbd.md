# images2PosedRGBD

POST /api/v2/tasks:images2PosedRGBD

Submit the images2PosedRGBD task



```sh
curl --request POST \
  --url 'https://api.atlas-beta.worldlabs.ai/api/v2/tasks:images2PosedRGBD?wait=true' \
  --header "WLT-Api-Key: $WLT_API_KEY" \
  --header 'Idempotency-Key: request-001' \
  --header 'Content-Type: application/json' \
  --data '{
  "base64Outputs": false,
  "frames": [
    {
      "imageAsset": {
        "assetId": "asset_01jexample000000000000000"
      }
    }
  ],
  "canonicalizeToFirstFrame": false,
  "targetResolution": [
    1280,
    720
  ],
  "refinePoses": false
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
          "depthAsset": {
            "assetId": "asset_01jexample000000000000000",
            "url": "https://example.com/depthAsset.exr"
          }
        },
        "centroidWorld": [
          1,
          1,
          1
        ]
      }
    ],
    "poseRefinementAccepted": false
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
    "/api/v2/tasks:images2PosedRGBD": {
      "post": {
        "tags": [
          "tasks"
        ],
        "summary": "Submit the images2PosedRGBD task",
        "operationId": "submit_images2PosedRGBD_api_v2_tasks_images2PosedRGBD_post",
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
                "$ref": "#/components/schemas/Images2PosedRGBDRequest"
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
                  "$ref": "#/components/schemas/Images2PosedRGBDResponseOperation"
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
      "Images2PosedRGBDRequest": {
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
          "base64Outputs": {
            "type": "boolean",
            "title": "Base64Outputs",
            "description": "When the task is answered at submission, return each output file as base64 in that response rather than by assetId and url. This skips storing the files before the answer and the caller's download after it. A task that is not answered at submission, and every later read of the operation, names the outputs by assetId and url either way.",
            "default": false
          },
          "frames": {
            "items": {
              "$ref": "#/components/schemas/FrameRGBAsset"
            },
            "type": "array",
            "minItems": 1,
            "title": "Frames",
            "description": "Ordered image inputs (min 1). A frame that carries a camera, a depth buffer or a mask is rejected rather than quietly ignored: none of them reaches the reconstruction."
          },
          "canonicalizeToFirstFrame": {
            "type": "boolean",
            "title": "Canonicalizetofirstframe",
            "description": "Place the first camera at the origin facing forward.",
            "default": false
          },
          "targetResolution": {
            "anyOf": [
              {
                "prefixItems": [
                  {
                    "type": "integer"
                  },
                  {
                    "type": "integer"
                  }
                ],
                "type": "array",
                "maxItems": 2,
                "minItems": 2,
                "items": {
                  "type": "integer"
                }
              },
              {
                "type": "null"
              }
            ],
            "title": "Targetresolution",
            "description": "Return the depth, confidence and camera intrinsics on this (width, height) pixel grid. The reconstruction is scaled to cover the requested size and center-cropped to it, so the result is exactly the size asked for and never stretched, and the intrinsics are updated with it -- unprojecting the returned depth with the returned camera gives the same geometry either way. A requested aspect that differs from the reconstruction's costs field of view, since the crop is what makes the size exact, and centroidWorld then describes the cropped view. Omit for the 1280 by 720 default; pass null to take the instance's own default.",
            "default": [
              1280,
              720
            ]
          },
          "refinePoses": {
            "type": "boolean",
            "title": "Refineposes",
            "description": "Bundle-adjust the estimated cameras against dense matches before answering. The backbone's poses are good to about half a degree, which is enough to reconstruct from and not enough to refine against: the residual shows up as blur wherever two views disagree. The solve anchors on the depth this task has just produced, so it costs a matcher pass and a solve rather than another reconstruction, and it needs two or more frames. A solve that moves the cameras further than the guards allow is thrown away and the unrefined reconstruction is returned, which is a success rather than an error.",
            "default": false
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "frames"
        ],
        "title": "Images2PosedRGBDRequest",
        "description": "Body of ``POST /api/v2/tasks:images2PosedRGBD``."
      },
      "Images2PosedRGBDResponseOperation": {
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
                "$ref": "#/components/schemas/Images2PosedRGBDResponse"
              },
              {
                "type": "null"
              }
            ],
            "description": "``Images2PosedRGBDResponse`` result when ``done`` is true and the task succeeded; null while running and after failure."
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
        "title": "Images2PosedRGBDResponseOperation",
        "description": "Long-running operation whose successful terminal ``response`` has type ``Images2PosedRGBDResponse``. This is the common Operation envelope with a task-specific response type, not a separate operation resource."
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
      "FrameRGBAsset": {
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
            "anyOf": [
              {
                "$ref": "#/components/schemas/PinholeCamera"
              },
              {
                "type": "null"
              }
            ],
            "description": "Optional camera-to-world pose and intrinsics."
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
          "imageAsset"
        ],
        "title": "FrameRGBAsset",
        "description": "A frame whose RGB image is always present; camera stays optional."
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
      "Images2PosedRGBDResponse": {
        "properties": {
          "frames": {
            "items": {
              "$ref": "#/components/schemas/Images2PosedRGBDPerImageResult"
            },
            "type": "array",
            "title": "Frames",
            "description": "One reconstructed frame per input image, in request order."
          },
          "poseRefinementAccepted": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "title": "Poserefinementaccepted",
            "description": "When refinePoses was requested, whether the refined cameras were kept. False means the original reconstruction was returned; null means refinement was not requested."
          }
        },
        "type": "object",
        "required": [
          "frames"
        ],
        "title": "Images2PosedRGBDResponse",
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
      "Images2PosedRGBDPerImageResult": {
        "properties": {
          "imageAsset": {
            "$ref": "#/components/schemas/TaskAsset",
            "description": "The source image the depth was estimated from."
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
            "$ref": "#/components/schemas/LinearDepthBufferAsset",
            "description": "Linear-depth EXR in world units, aligned to camera, beside a confidence map. Multiple frames carry the calibrated keep-probability ('ultimate'); a single frame carries the backbone's own mask ('model'), the only score one view can support. Unproject the depth with the camera intrinsics to recover camera-space points in Three.js convention."
          },
          "centroidWorld": {
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
            "title": "Centroidworld",
            "description": "Ground-plane pivot formed from the mean finite camera-space point transformed into world space and projected to y=0.",
            "items": {
              "type": "number"
            }
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "imageAsset",
          "camera",
          "depth",
          "centroidWorld"
        ],
        "title": "Images2PosedRGBDPerImageResult",
        "description": "Per-image reconstruction output.\n\nGeometry is the depth EXR: unproject it with ``camera`` to recover the\ncamera-space point cloud. ``camera``'s intrinsics describe the depth grid,\nwhich is whatever grid the backbone reconstructed on, so they are not\nnecessarily the intrinsics of ``imageAsset``."
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

