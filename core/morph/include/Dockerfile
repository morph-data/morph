# Base image for Morph Cloud
FROM public.ecr.aws/i1l4z0u0/morph-cloud:python${MORPH_PYTHON_VERSION}

# Set working directory
WORKDIR /var/task

# Install Python dependencies with poetry
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target "${MORPH_TASK_ROOT}"

# Copy source code and dependencies
COPY .morph/frontend/dist /var/task/.morph/frontend/dist
COPY .morph/core /var/task/core
COPY .morph/meta.json .morph/
COPY morph_project.yml .
COPY data ./data
COPY src ./src

# Command to run the Lambda function
CMD ["core.morph.api.app.handler"]
