# syntax=docker/dockerfile:1

# --- Build stage ---
FROM node:20-slim AS builder

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --silent

COPY frontend/ .
ARG REACT_APP_API_BASE_URL=http://localhost:5000
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
RUN npm run build

# --- Runtime stage ---
FROM nginx:alpine AS runtime

COPY --from=builder /app/build /usr/share/nginx/html

# Custom nginx config for SPA routing
RUN printf 'server {\n\
    listen 3000;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
