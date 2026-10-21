# API reference

Endpoints, request fields, response schemas, and examples from the Marble 2 Developer API.

- [List assets](/docs/api-reference/list-assets) — GET /api/v2/assets
- [Create asset](/docs/api-reference/create-asset) — POST /api/v2/assets
- [Create read prefix](/docs/api-reference/create-read-prefix) — POST /api/v2/assets:createReadPrefix
- [Delete asset](/docs/api-reference/delete-asset) — DELETE /api/v2/assets/{asset}
- [Get asset](/docs/api-reference/get-asset) — GET /api/v2/assets/{asset}
- [Complete upload](/docs/api-reference/complete-upload) — POST /api/v2/assets/{asset}:completeUpload
- [Create read URL](/docs/api-reference/create-read-url) — POST /api/v2/assets/{asset}:createReadUrl
- [Create upload URL](/docs/api-reference/create-upload-url) — POST /api/v2/assets/{asset}:createUploadUrl
- [Create upload URLs](/docs/api-reference/create-upload-urls) — POST /api/v2/assets/{asset}:createUploadUrls
- [Health check](/docs/api-reference/health-check) — GET /api/v2/health
- [List operations](/docs/api-reference/list-operations) — GET /api/v2/operations
- [Get operation](/docs/api-reference/get-operation) — GET /api/v2/operations/{operation}
- [Cancel operation](/docs/api-reference/cancel-operation) — POST /api/v2/operations/{operation}:cancel
- [Get operation trace](/docs/api-reference/get-operation-trace) — GET /api/v2/operations/{operation}:trace
- [Wait for operation](/docs/api-reference/wait-for-operation) — POST /api/v2/operations/{operation}:wait
- [Get webhook delivery](/docs/api-reference/get-webhook-delivery) — GET /api/v2/operations/{operation}/webhookDelivery
- [atlasChisel](/docs/api-reference/atlas-chisel) — POST /api/v2/tasks:atlasChisel
- [atlasGenerate](/docs/api-reference/atlas-generate) — POST /api/v2/tasks:atlasGenerate
- [atlasMasked](/docs/api-reference/atlas-masked) — POST /api/v2/tasks:atlasMasked
- [atlasTextToImage](/docs/api-reference/atlas-text-to-image) — POST /api/v2/tasks:atlasTextToImage
- [images2PosedRGBD](/docs/api-reference/images2-posed-rgbd) — POST /api/v2/tasks:images2PosedRGBD
- [splats2Mesh](/docs/api-reference/splats2-mesh) — POST /api/v2/tasks:splats2Mesh