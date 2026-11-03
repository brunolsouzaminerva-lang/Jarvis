# Plano de integração Jarvis + Codex

1. Obter autorização para uso de código e dados corporativos na nuvem.
2. Importar somente código revisado, sem segredos ou dados de produção.
3. Isolar automações de Dux, Excel, validação e versionamento.
4. Adicionar testes com dados sintéticos para engenharia, controladoria e tabelas dinâmicas.
5. Configurar revisão por pull request e testes de integração em ambiente corporativo autorizado.
6. Não automatizar implantação em produção sem aprovação.

A workflow de CI executa testes, **não** inicia o Codex automaticamente nem opera o Dux.
