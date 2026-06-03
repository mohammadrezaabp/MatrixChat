FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy application code
COPY . .

# Build Next.js app for production
RUN npm run build

# Expose port
EXPOSE 3000

ENV NODE_ENV=production

# Run the application in production mode
CMD ["npm", "run", "start", "--", "-H", "0.0.0.0", "-p", "3000"]
