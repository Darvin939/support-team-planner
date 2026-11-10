FROM docker-dev.registry-ci.delta.mysecure_57117ba4eem0.ru/ubi8/python-312:latest

USER 0
WORKDIR /app

COPY pip.conf pip.conf
ENV PIP_CONFIG_FILE=./pip.conf

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY support_planner.py application_version.json changelog.json app_build_metadata.json ./
COPY backend/ backend/
COPY frontend/dist/ frontend/dist/
COPY scripts/__init__.py scripts/migrate_database.py scripts/import_sqlite_to_postgres.py scripts/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN test -f frontend/dist/index.html \
    && test -f frontend/dist/taskTransitions.json \
    && chown -R 1001:0 /app \
    && chmod 0755 /app \
    && chmod 1777 /tmp

USER 1001:0
EXPOSE 5093

ENTRYPOINT []
CMD ["python", "support_planner.py"]
