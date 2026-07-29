FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
COPY og.png /usr/share/nginx/html/og.png
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
