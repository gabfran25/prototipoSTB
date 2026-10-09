# prototipoSTB

```mermaid
graph TD
    classDef client fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#01579b;
    classDef service fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#2e7d32;
    classDef eureka fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#7b1fa2;

    subg["PC Cliente / Desarrollador"]
    Client[("💻 Postman Client")]:::client
    end

    subg2["PC Servidor (IP: 10.10.203.255)"]
    subg3["Contenedor / Instancia 2"]
    Item["📦 Servicio Items<br/>Puerto: 8002"]:::service
    end

    subg4["Contenedor / Instancia 1"]
    Prod["📦 Servicio Productos<br/>Puerto: 8001"]:::service
    end

    subg5["Spring Cloud"]
    Eureka["🔍 Eureka Server"]:::eureka
    end
    end

    Client -- "GET /listar (Port 8002)" --> Item
    Item -- "RestTemplate / Feign<br/>(IP: 10.10.203.255:8001)" --> Prod
    Prod -. "Registro de Instancia (UP)" .-> Eureka

    style subg fill:#f9f9f9,stroke:#ccc,stroke-width:2px
    style subg2 fill:#fff,stroke:#333,stroke-width:2px,stroke-dasharray: 5 5
    style subg3 fill:#fafafa,stroke:#bbb,stroke-width:1px
    style subg4 fill:#fafafa,stroke:#bbb,stroke-width:1px
    style subg5 fill:#fafafa,stroke:#bbb,stroke-width:1px
