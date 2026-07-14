FROM python:3.14-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Prophet is optional and skipped in the container build by default since its
# cmdstanpy build step needs a C++ toolchain. Uncomment the two lines below if
# you want it baked into the image (adds build time + image size):
# COPY requirements-optional.txt .
# RUN apt-get update && apt-get install -y --no-install-recommends g++ && \
#     pip install --no-cache-dir -r requirements-optional.txt && \
#     apt-get purge -y g++ && apt-get autoremove -y

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
