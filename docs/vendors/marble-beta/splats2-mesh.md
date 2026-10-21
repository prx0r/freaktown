# splats2Mesh

POST /api/v2/tasks:splats2Mesh

Submit the splats2Mesh task



```sh
curl --request POST \
  --url 'https://api.atlas-beta.worldlabs.ai/api/v2/tasks:splats2Mesh?wait=true' \
  --header "WLT-Api-Key: $WLT_API_KEY" \
  --header 'Idempotency-Key: request-001' \
  --header 'Content-Type: application/json' \
  --data '{
  "textureMode": "image_texture",
  "textureSize": 4096,
  "splatAsset": {
    "assetId": "asset_01jexample000000000000000"
  }
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
    "mesh": {
      "assetId": "asset_01jexample000000000000000",
      "url": "https://example.com/mesh.png"
    },
    "anchorPositions": [
      [
        1,
        1,
        1
      ]
    ],
    "metadata": {}
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
    "/api/v2/tasks:splats2Mesh": {
      "post": {
        "tags": [
          "tasks"
        ],
        "summary": "Submit the splats2Mesh task",
        "operationId": "submit_splats2Mesh_api_v2_tasks_splats2Mesh_post",
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
                "$ref": "#/components/schemas/Splats2MeshRequest"
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
                  "$ref": "#/components/schemas/Splats2MeshResponseOperation"
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
      "Splats2MeshRequest": {
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
          "cameras": {
            "anyOf": [
              {
                "items": {
                  "$ref": "#/components/schemas/PinholeCamera"
                },
                "type": "array",
                "maxItems": 512,
                "minItems": 1
              },
              {
                "oneOf": [
                  {
                    "$ref": "#/components/schemas/CamerasManualAnchors"
                  },
                  {
                    "$ref": "#/components/schemas/CamerasAutoAnchors"
                  },
                  {
                    "$ref": "#/components/schemas/CamerasExteriorSphere"
                  }
                ],
                "discriminator": {
                  "propertyName": "strategy",
                  "mapping": {
                    "auto_anchors": "#/components/schemas/CamerasAutoAnchors",
                    "exterior_sphere": "#/components/schemas/CamerasExteriorSphere",
                    "manual_anchors": "#/components/schemas/CamerasManualAnchors"
                  }
                }
              },
              {
                "type": "null"
              }
            ],
            "title": "Cameras",
            "description": "Cameras the splats are rendered from. The surface is reconstructed from those renders, so geometry no camera sees is not meshed. Name a strategy -- `auto_anchors` (the default) finds viewpoints in the scene's free space, `manual_anchors` takes them from the request, `exterior_sphere` rings the scene from outside for an object or turntable capture -- or pass a list of cameras to render as given, at most 512, sharing one width and height between 64 and 1024 that becomes the render resolution."
          },
          "advancedOptions": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/Splats2MeshAdvancedOptions"
              },
              {
                "type": "null"
              }
            ],
            "description": "Finer control over how the splats are rendered and how the surface is extracted. Omit for the defaults."
          },
          "orientedBoundingBox": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/Splats2MeshOrientedBoundingBox"
              },
              {
                "type": "null"
              }
            ],
            "description": "Region to extract, as an oriented box in Three.js coordinates. Omit to mesh the whole scene."
          },
          "targetFaces": {
            "anyOf": [
              {
                "type": "integer",
                "minimum": 1
              },
              {
                "type": "null"
              }
            ],
            "title": "Targetfaces",
            "description": "Decimate the extracted mesh to at most this many faces. A target above the extracted count does nothing. Omit to keep every face."
          },
          "textureMode": {
            "type": "string",
            "enum": [
              "image_texture",
              "vertex_color",
              "none"
            ],
            "title": "Texturemode",
            "description": "Mesh appearance: 'image_texture' projects rendered views onto a UV atlas, 'vertex_color' bakes per-vertex colors, and 'none' leaves the mesh untextured.",
            "default": "image_texture"
          },
          "textureSize": {
            "type": "integer",
            "maximum": 8192,
            "minimum": 1,
            "title": "Texturesize",
            "description": "Height and width of the texture atlas, in pixels, for `image_texture` mode. One rendered view plus its border has to fit, so this must be at least 2% above the render size in play: the larger render bank under the anchor strategies, `renderHw` under `exterior_sphere`, or the supplied cameras' own size.",
            "default": 4096
          },
          "splatAsset": {
            "$ref": "#/components/schemas/TaskAsset",
            "description": "The Gaussian splat scene (.spz) to mesh. Inline base64 must carry a `data:` prefix to declare its media type: asset creation otherwise infers the type from the bytes, and the sniffer knows image formats only."
          }
        },
        "type": "object",
        "required": [
          "splatAsset"
        ],
        "title": "Splats2MeshRequest",
        "description": "Body of a splats2Mesh request."
      },
      "Splats2MeshResponseOperation": {
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
                "$ref": "#/components/schemas/Splats2MeshResponse"
              },
              {
                "type": "null"
              }
            ],
            "description": "``Splats2MeshResponse`` result when ``done`` is true and the task succeeded; null while running and after failure."
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
        "title": "Splats2MeshResponseOperation",
        "description": "Long-running operation whose successful terminal ``response`` has type ``Splats2MeshResponse``. This is the common Operation envelope with a task-specific response type, not a separate operation resource."
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
      "CamerasManualAnchors": {
        "properties": {
          "strategy": {
            "type": "string",
            "const": "manual_anchors",
            "title": "Strategy"
          },
          "anchors": {
            "items": {
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
              "items": {
                "type": "number"
              }
            },
            "type": "array",
            "maxItems": 64,
            "minItems": 1,
            "title": "Anchors",
            "description": "Anchor positions in Three.js coordinates (+X right, +Y up, -Z forward)."
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "strategy",
          "anchors"
        ],
        "title": "CamerasManualAnchors",
        "description": "Render from explicitly placed anchor positions.\n\nA cubemap is rendered at each anchor, and more cameras are sampled around\nit. Anchors belong in open space, with a clear view of the regions that\nmatter most."
      },
      "CamerasAutoAnchors": {
        "properties": {
          "strategy": {
            "type": "string",
            "const": "auto_anchors",
            "title": "Strategy"
          },
          "oriented": {
            "type": "boolean",
            "title": "Oriented",
            "description": "Judge a candidate by whether the surface faces it, which needs splats whose normals are oriented -- usually only true if they were optimized for it. Leave false to judge by enclosure alone, which is safe on any scene.",
            "default": false
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "strategy"
        ],
        "title": "CamerasAutoAnchors",
        "description": "Find anchor positions automatically, then render from them.\n\nCandidates come from the free space the geometry encloses, and `oriented`\npicks which rule judges one valid. The default when a request names no\ncameras."
      },
      "CamerasExteriorSphere": {
        "properties": {
          "strategy": {
            "type": "string",
            "const": "exterior_sphere",
            "title": "Strategy"
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "strategy"
        ],
        "title": "CamerasExteriorSphere",
        "description": "Render from a sphere around the splats, looking inward.\n\nFor anything whose surface can be seen from outside -- an object, a turntable\ncapture -- no anchors are needed. Cameras are spread evenly over a sphere\nbounding the splats and aimed at its center. Naming an\n`orientedBoundingBox` sizes that sphere on the splats inside it, which is\nwhat picks one object out of a larger capture."
      },
      "Splats2MeshAdvancedOptions": {
        "properties": {
          "renderHw": {
            "type": "integer",
            "maximum": 1024,
            "minimum": 64,
            "title": "Renderhw",
            "description": "Height and width of the main views rendered to measure the splat surface and texture it, in pixels.",
            "default": 1024
          },
          "renderHwSecondary": {
            "type": "integer",
            "maximum": 1024,
            "minimum": 64,
            "title": "Renderhwsecondary",
            "description": "Height and width of the secondary views, in pixels. The anchor strategies sample extra cameras around each anchor and render them here, covering what the main views miss. `exterior_sphere` and a supplied camera list render no secondary views and ignore this.",
            "default": 640
          },
          "normalSource": {
            "type": "string",
            "enum": [
              "depth",
              "render"
            ],
            "title": "Normalsource",
            "description": "Normals orient the implicit surface the mesh is extracted from. `depth` estimates them from the rendered depth; `render` aggregates the splats' own, which assumes each splat's local z axis points along the surface normal.",
            "default": "depth"
          },
          "depthSource": {
            "type": "string",
            "enum": [
              "render",
              "stereo"
            ],
            "title": "Depthsource",
            "description": "Depth of the main views. `render` uses the splats' rendered depth; `stereo` measures it by stereo matching each view against a second render from a camera shifted sideways, which is sharper where the splats are fuzzy and slower to compute. Pixels stereo cannot match keep the rendered depth.",
            "default": "render"
          },
          "resolution": {
            "type": "integer",
            "maximum": 8192,
            "minimum": 64,
            "title": "Resolution",
            "description": "Resolution of the grid the implicit surface is built on, across the region's longest side. Powers of two only. This sets the finest detail the mesh can carry.",
            "default": 512
          },
          "trimQuantile": {
            "type": "number",
            "exclusiveMaximum": 1,
            "minimum": 0,
            "title": "Trimquantile",
            "description": "Drop vertices whose sample density falls below this quantile. Reconstruction closes the surface over regions it saw no samples in, and trimming cuts that invented skin back off. 0 keeps every vertex.",
            "default": 0
          }
        },
        "additionalProperties": false,
        "type": "object",
        "title": "Splats2MeshAdvancedOptions",
        "description": "Advanced reconstruction controls for custom mesh generation."
      },
      "Splats2MeshOrientedBoundingBox": {
        "properties": {
          "center": {
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
            "title": "Center",
            "description": "Center of the region, in world space.",
            "items": {
              "type": "number"
            }
          },
          "orientation": {
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
            "title": "Orientation",
            "description": "Rotation of the region away from the world axes, as an xyzw quaternion.",
            "items": {
              "type": "number"
            }
          },
          "halfExtents": {
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
            "title": "Halfextents",
            "description": "Half the region's size along each of its own axes. All three must be positive.",
            "items": {
              "type": "number"
            }
          }
        },
        "additionalProperties": false,
        "type": "object",
        "required": [
          "center",
          "orientation",
          "halfExtents"
        ],
        "title": "Splats2MeshOrientedBoundingBox",
        "description": "Region to extract, as an oriented box in Three.js coordinates."
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
      "Splats2MeshResponse": {
        "properties": {
          "mesh": {
            "$ref": "#/components/schemas/TaskAsset",
            "description": "The generated GLB mesh."
          },
          "anchorPositions": {
            "anyOf": [
              {
                "items": {
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
                  "items": {
                    "type": "number"
                  }
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "title": "Anchorpositions",
            "description": "Anchor positions the cameras were generated from, in Three.js coordinates. Null when no anchors were used: cameras were supplied directly, or `exterior_sphere` was chosen."
          },
          "metadata": {
            "additionalProperties": {
              "type": "string"
            },
            "type": "object",
            "title": "Metadata",
            "description": "Deprecated runtime diagnostics. Informational only -- keys are not part of the contract and may change.",
            "deprecated": true
          }
        },
        "type": "object",
        "required": [
          "mesh"
        ],
        "title": "Splats2MeshResponse",
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

