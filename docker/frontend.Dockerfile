# syntax=docker/dockerfile:1

FROM node:20-bullseye AS build
WORKDIR /app

# The Vue build only needs the JavaScript toolchain.  Server-side native
# modules are not required here, so we skip their install scripts to avoid
# pulling in Python and a C++ toolchain.

COPY package.json package-lock.json ./
RUN npm_config_ignore_scripts=1 npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
RUN rm -f /etc/nginx/conf.d/default.conf \
    && rm -f /etc/nginx/templates/default.conf.template
COPY docker/nginx.conf /etc/nginx/conf.d/app.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx","-g","daemon off;"]
