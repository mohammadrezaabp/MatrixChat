FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies with npm
RUN npm ci

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Set environment variable for Next.js
ENV NODE_ENV=development

# Run the application in dev mode for localhost development
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
