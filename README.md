# miso-gallery

A lightweight Flask image gallery with browse and delete functionality.

## Features

- **Folder Navigation** - Browse through nested folder structures
- **Image Grid View** - Clean dark-mode grid of images
- **Delete Capability** - Remove images directly from the UI
- **Responsive** - Works on desktop and mobile

## Quick Start

```bash
# Run with Docker
docker run -p 5000:5000 -v /path/to/images:/data ghcr.io/joryirving/miso-gallery:latest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_FOLDER` | `/data` | Path to images directory |
| `IMAGE_BASE_URL` | - | Base URL for sharing image links |
| `PORT` | `5000` | Server port |

## Deployment

### Docker Compose

```yaml
services:
  miso-gallery:
    image: ghcr.io/joryirving/miso-gallery:latest
    ports:
      - "5000:5000"
    volumes:
      - ./images:/data
    environment:
      - IMAGE_BASE_URL=https://your-cdn.example.com/images
```

### Kubernetes

```yaml
# Add to your HelmRelease
containers:
  miso-gallery:
    image: ghcr.io/joryirving/miso-gallery:latest
    volumes:
      data:
        mountPath: /data
```

## Development

```bash
# Local development
pip install -r requirements.txt
python app.py
```

## License

MIT
