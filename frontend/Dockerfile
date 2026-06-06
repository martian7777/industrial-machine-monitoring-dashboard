# Vite dev server (matches the plan: frontend runs in dev mode on 5173).
# For a production build, swap to a multi-stage build + nginx (see powerbi/README
# notes), or run `npm run build && npm run preview`.
FROM node:20-alpine

WORKDIR /app

COPY package.json ./
# Use install (not ci) since this repo ships without a committed lockfile.
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
