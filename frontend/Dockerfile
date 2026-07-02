FROM nginx:alpine

# Remove default nginx website
RUN rm -rf /usr/share/nginx/html/*

COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend files
COPY . /usr/share/nginx/html/

# Expose nginx port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]