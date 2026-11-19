# Consulta FIPE com histórico e alertas

Aplicação web em Flask que consulta a tabela FIPE pela API pública (fipe.online), guarda o histórico de preços em SQLite e permite criar alertas de preço-alvo. Não usa IA nem chave de API paga.

```
Navegador → Flask (app.py) → fipe.py → API da FIPE
                 ↓
            db.py (SQLite: preços e alertas)  ←  verificar_alertas.py (agendável)
```

## Como rodar (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra http://127.0.0.1:5000, escolha tipo, marca, modelo e ano, e clique em **Consultar preço**.

## Alertas

Crie o alerta pela página e rode, à mão ou agendado:

```bat
python verificar_alertas.py
```

Quando o preço FIPE chega ao alvo, o aviso aparece no terminal e é gravado em `alertas.log`. Cada alerta avisa uma vez por mês de referência. Como a FIPE atualiza mensalmente, rodar uma vez por semana basta.

Para agendar no Windows: *Agendador de Tarefas → Criar Tarefa Básica →* programa `.venv\Scripts\python.exe`, argumentos `verificar_alertas.py`, e "Iniciar em" a pasta do projeto.

## Decisões de projeto

- **Cache em memória** das listas (24 h) e do preço (6 h): o preço só muda uma vez por mês, então repetir consulta não gasta a cota da API.
- **Um registro por mês** no SQLite (`UNIQUE` em veículo + referência), então consultar de novo não duplica.
- **Validação dos ids** antes de montar a URL da API, para ninguém injetar caminhos.
- **Front sem XSS:** a página monta tudo com `textContent`, nunca `innerHTML`.
- **Histórico:** vem da própria API (pode ser curto no plano gratuito) e é complementado pelas consultas que você faz ao longo dos meses.

## Limitações

- Depende de um serviço gratuito de terceiros que pode mudar ou limitar o uso.
- A FIPE é preço de referência, não preço de anúncio.

## Próximos passos

- [ ] Deploy (Render, Railway) e GIF de demonstração aqui no README
- [ ] Aviso por e-mail ou Telegram nos alertas
- [ ] Gráfico do histórico
