# Base image for AWS Lambda
FROM public.ecr.aws/lambda/python:3.9

RUN yum install -y \
    postgresql-devel \
    gcc \
    gcc-c++ && \
    yum clean all

# Set working directory
WORKDIR /var/task

# Install Python dependencies with poetry
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy source code and dependencies
COPY .morph/frontend/dist /var/task/.morph/frontend/dist
COPY .morph/core /var/task/core
COPY .morph/meta.json .morph/
COPY morph_project.yml .
COPY src ./src

# Command to run the Lambda function
CMD ["core.morph.api.app.handler"]
