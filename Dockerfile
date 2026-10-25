FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=3000
WORKDIR /app
COPY *.py /app/
COPY tools /app/tools
COPY capture /app/capture
COPY local /app/local
RUN python tools/build_local.py && python tools/build_account.py && mkdir -p /app/data \
    && groupadd --gid 10001 cashlarp && useradd --uid 10001 --gid cashlarp --no-create-home cashlarp \
    && chown -R cashlarp:cashlarp /app/data
USER cashlarp
EXPOSE 3000
VOLUME /app/data
CMD ["python", "server.py", "--host", "0.0.0.0", "--db", "/app/data/sandbox.sqlite3"]
