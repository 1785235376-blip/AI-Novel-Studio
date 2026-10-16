# Only the enumerated PUBLIC runtime reaches the final image. Private extensions
# belong outside these roots; a new core file/dependency requires manifest review.
FROM python:3.12-slim AS public-source
WORKDIR /source
COPY pyproject.toml .
COPY app ./app
COPY local_interop_protocol ./local_interop_protocol
COPY local_interop_desktop ./local_interop_desktop
COPY contracts ./contracts
COPY release/version.json ./release/version.json
COPY config ./config
COPY prompts ./prompts
COPY workflows ./workflows
COPY packaging/public-build.json ./packaging/public-build.json
COPY scripts/public_build.py ./scripts/public_build.py
RUN python -B scripts/public_build.py --source /source --stage /public --docker --receipt /public-build-receipt.json

FROM python:3.12-slim
WORKDIR /app
COPY --from=public-source /public/ ./
COPY --from=public-source /public-build-receipt.json ./release/public-build-receipt.json
RUN pip install --no-cache-dir .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
