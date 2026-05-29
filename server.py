from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import json
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}},
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"])

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PROMPT_NF = """Voce e especialista em documentos fiscais brasileiros da empresa DI GASPI (rede de calcados).

CONTEXTO:
- A DI GASPI e sempre o TOMADOR (quem pagou). Nunca e o fornecedor.
- O FORNECEDOR e quem emitiu a nota e recebeu o pagamento.
- Nas notas ha anotacoes manuscritas com: P: (pedido), F: (fornecedor/numero), V: (vencimento)

=== REGRA 1: CNPJ DO TOMADOR ===
Faca uma varredura completa no documento procurando o CNPJ da DI GASPI (tomador).
Locais para procurar (em ordem de prioridade):
1. Secao "TOMADOR DO SERVICO" ou "DADOS DO TOMADOR" -> campo CNPJ/CPF/NIF
2. Secao "DESTINATARIO" -> campo CNPJ
3. Secao "INTERMEDIARIO DO SERVICO NAO IDENTIFICADO NA NFS-e" -> campo CNPJ
4. Qualquer campo CNPJ associado ao nome "GASPI", "GASPARI", "DI GASPI" ou "COMERCIO DE CALCADOS"
5. Anotacao manuscrita "F:" pode conter o codigo da loja (use para confirmar)
Retorne SOMENTE os 14 digitos numericos, sem formatacao.

=== REGRA 2: NUMERO DO DOCUMENTO ===
Todo documento fiscal tem um numero. Faca varredura completa:
- NFS-e: campo "Numero da NFS-e", "Numero da Nota", numero pequeno no canto (ex: 1032, 55, 338)
- NF-e/DANFE: campo "NF Nr", numero no cabecalho superior (ex: 14800)
- FATURA: "NOTA FISCAL FATURA Nr XXXXXX" -> use apenas os digitos significativos (ex: 793)
- RECIBO: procure qualquer numero de identificacao, serie, protocolo ou recibo
- DARF: numero do documento de arrecadacao
- Anotacao manuscrita "P:" pode conter o numero do pedido como alternativa
NUNCA use a chave de acesso (sequencia de 44 digitos).
Se absolutamente nao houver numero, use o numero do pedido e marque eh_pedido:true.

=== REGRA 3: FORNECEDOR (EMITENTE) ===
Quem EMITIU a nota e recebeu o pagamento:
- NFS-e: secao "EMITENTE DA NFS-e", "DADOS DO PRESTADOR", "PRESTADOR DO SERVICO"
- NF-e: secao "EMITENTE", "REMETENTE", "DADOS DO EMITENTE"
- NUNCA use: nome da Di Gaspi, Gaspari, nome de cidade, estado, "TOMADOR", "DESTINATARIO"
- Nome curto sem LTDA/ME/EPP/EIRELI/SA, maximo 28 caracteres

=== REGRA 4: VENCIMENTO ===
Procure em ordem:
1. Anotacao manuscrita "V:" seguida de data (ex: "V: 15/06" -> "15-06")
2. Campo impresso "Vencimento", "Data de Vencimento", "Pagar ate"
3. Para DARF: campo "Pagar ate" ou "Vencimento"
Formato de saida: DD-MM (apenas dia e mes)

=== REGRA 5: ROTACAO ===
0=correto, 180=cabeca para baixo, 90=virado direita, 270=virado esquerda

Retorne APENAS este JSON sem markdown ou explicacoes:
{"tipo":"NFSe","numero_documento":"123","eh_pedido":false,"fornecedor_curto":"NOME","cnpj_tomador":"00000000000000","valor":0.00,"vencimento":"DD-MM","rotacao":0}

tipo: NFSe, NFe, fatura, recibo, DARF, outro"""


@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response


@app.route("/health", methods=["GET", "OPTIONS"])
def health():
    return jsonify({"status": "ok"})


@app.route("/read-nf", methods=["POST", "OPTIONS"])
def read_nf():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    try:
        data = request.get_json()
        pdf_b64 = data.get("pdf_base64")
        if not pdf_b64:
            return jsonify({"error": "pdf_base64 obrigatorio"}), 400

        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": PROMPT_NF
                    }
                ]
            }]
        )

        text = "".join(b.text for b in message.content if hasattr(b, "text"))
        clean = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        return jsonify({"success": True, "data": parsed})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
