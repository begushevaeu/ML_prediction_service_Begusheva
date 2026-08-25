# ML Models

Step 6 adds model upload and ownership-aware model metadata.

## Upload Flow

1. The user authenticates with a bearer token.
2. The user uploads a multipart model file with `POST /api/v1/models`.
3. The API enforces the configured file size limit.
4. The API accepts `.joblib`, `.pkl`, and `.pickle` artifacts.
5. The API loads the artifact and checks for a callable `predict` method.
6. The file is stored under `MODEL_STORAGE_PATH`.
7. Metadata is saved in the `ml_models` table.

The default upload size limit is `10 MiB` and can be changed with
`MAX_MODEL_UPLOAD_SIZE_BYTES`.

## Metadata

Stored model metadata includes:

- original uploaded filename;
- uploaded file size;
- Python model type;
- optional user metadata from `metadata_json`.

## MVP Trust Boundary

Pickle and joblib files can execute Python code while loading. In this local MVP,
the upload endpoint is intended for trusted artifacts created by the project
owner or test users. Production hardening should isolate model validation in a
sandboxed worker process before accepting untrusted uploads.

## Deferred Work

This step does not execute predictions. Step 7 connects uploaded models to
asynchronous prediction tasks and billing.
