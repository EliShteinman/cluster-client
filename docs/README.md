# Documentation

| Page | Read it to |
|---|---|
| [../README.md](../README.md) | Install, run, call, test, build and deploy |
| [architecture.md](architecture.md) | Understand the goal, the chain of services, one call, startup and the modules |
| [failures.md](failures.md) | Know every failure: status, `x-edge-error`, headers, whether the call reached the target, and where it is logged |
| [configuration.md](configuration.md) | Find or change a setting |
| [deployment.md](deployment.md) | Deploy with Helm: values, pod, volumes, environment, the collector and Elastic |
| [../AGENTS.md](../AGENTS.md) | Change the code (the guide for AI agents and for people) |

## Diagrams

Each diagram is a `.drawio` file (open it in draw.io) and a PNG of it next to it.

| Diagram | Shows |
|---|---|
| [context](diagrams/context.drawio.png) | Manager → NGINX → DataPower → cluster-client → target, and what each adds or checks |
| [happy-path](diagrams/happy-path.drawio.png) | The happy path only: the five steps of a call that works, the modules and data between them; each failure is a stub |
| [flow](diagrams/flow.drawio.png) | The request flow with every branch, every failure and where it is logged |
| [sequence](diagrams/sequence.drawio.png) | One successful and one rejected call, with `traceparent` and `traceresponse` |
| [class-diagram](diagrams/class-diagram.drawio.png) | Every module of `app/`, its functions, models, errors and settings, by import layer |
| [startup](diagrams/startup.drawio.png) | What the service checks when it starts, and why it stops |
| [deployment](diagrams/deployment.drawio.png) | The pod, its containers and volumes, environment from values, Elastic |

To export a diagram again after editing it (draw.io desktop):

```bash
drawio -x -f png -e -b 20 -o docs/diagrams/flow.drawio.png docs/diagrams/flow.drawio
```

## History

`proposals/` holds earlier proposals, kept as history. They describe decisions at the time they were written; the
code and the pages above describe the service as it is now.

- [proposals/coding-rules-and-cleanup.md](proposals/coding-rules-and-cleanup.md)
- [proposals/error-body-contract.md](proposals/error-body-contract.md)
