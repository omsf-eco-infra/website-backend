FROM public.ecr.aws/lambda/python:3.13

RUN dnf install -y git && dnf clean all

COPY pyproject.toml ${LAMBDA_TASK_ROOT}/pyproject.toml
COPY src ${LAMBDA_TASK_ROOT}/src

RUN pip install --no-cache-dir ${LAMBDA_TASK_ROOT}

COPY modules/fargate-compute/lambda/lambda_handler.py ${LAMBDA_TASK_ROOT}/lambda_handler.py

CMD ["lambda_handler.task_available_handler"]
