FROM node:22-alpine

WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web/ ./

ENV VITE_API_PROXY=http://api:8765
EXPOSE 5180

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5180", "--strictPort"]
