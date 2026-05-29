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

PROMPT_NF = """Voce e especialista em documentos fiscais brasileiros da empresa DI GASPI (redes de calcados).

CONTEXTO IMPORTANTE:
- A DI GASPI e o TOMADOR DO SERVICO (quem pagou/contratou). Ignore ela como fornecedor.
- O FORNECEDOR e quem EMITIU a nota e RECEBEU o pagamento.
- Nas notas ha anotacoes escritas a mao com os codigos: P: (pedido), F: (fornecedor), V: (vencimento)

REGRAS CRITICAS:

1. FORNECEDOR (emitente):
   - E quem EMITIU a nota. Campos: "EMITENTE DA NFS-e", "PRESTADOR DO SERVICO", "DADOS DO PRESTADOR", "Razao Social" do prestador
   - NUNCA use: nome da Di Gaspi, Gaspari, nome de cidade, nome de estado, "TOMADOR", "DESTINATARIO"
   - Use o nome curto sem LTDA/ME/EPP/EIRELI, maximo 28 caracteres

2. CNPJ DO TOMADOR:
   - E o CNPJ de quem RECEBEU o servico: "TOMADOR DO SERVICO", "DESTINATARIO", "DADOS DO TOMADOR"
   - Campos tipicos: "CNPJ/CPF / NIF" do tomador, "Inscricao Municipal" do tomador
   - Retorne SOMENTE os digitos, sem pontos ou tracos (14 digitos)
   - NUNCA use o CNPJ do emitente/prestador

3. NUMERO DA NOTA:
   - NFS-e: campo "Numero da NFS-e" ou "Numero da Nota" (numero pequeno, ex: 1032, 55, 338)
   - NF-e: campo "NF Nr" ou numero no canto superior (ex: 14800, 14799)
   - FATURA: numero da fatura no cabecalho (ex: "NOTA FISCAL FATURA Nr 000000793" -> use "793")
   - RECIBO sem numero: use o numero do pedido e marque eh_pedido:true
   - DARF: numero do documento
   - NUNCA use a chave de acesso (numero de 44 digitos)

4. VENCIMENTO:
   - Procure anotacoes manuscritas com "V:" seguido de data (ex: "V: 15/06" ou "V: 15-06")
   - Se nao houver "V:", procure campo "Data de Vencimento", "Vencimento", "Pagar ate"
   - Formato de saida: DD-MM (apenas dia e mes, ex: "15-06")

5. ROTACAO:
   - 0 = documento ja esta na posicao correta para leitura
   - 180 = documento esta de cabeca para baixo (texto invertido)
   - 90 = documento esta virado 90 graus para direita
   - 270 = documento esta virado 90 graus para esquerda

Retorne APENAS este JSON sem markdown:
{"tipo":"NFSe","numero_documento":"123","eh_pedido":false,"fornecedor_curto":"NOME EMITENTE","cnpj_tomador":"00000000000000","valor":0.00,"vencimento":"DD-MM","rotacao":0}

tipo pode ser: NFSe, NFe, fatura, recibo, DARF, outro"""


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
