FROM node:22-alpine AS build
WORKDIR /ui
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=build /ui/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
