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

PROMPT_NF = (
    "Voce e especialista em documentos fiscais brasileiros. "
    "Analise este documento e retorne APENAS JSON valido, sem markdown.\n\n"
    "REGRAS DE NUMERACAO:\n"
    "- NFS-e: campo Numero da NFS-e ou Numero da Nota\n"
    "- NF-e: campo NF Nr ou Numero\n"
    "- FATURA: use o numero da fatura (ex: NOTA FISCAL FATURA Nr 000000793 usa 793)\n"
    "- RECIBO sem numero: use numero do pedido e marque eh_pedido:true\n"
    "- DARF: numero do documento de arrecadacao\n\n"
    "EMITENTE = quem assina/emite (quem recebe o dinheiro)\n"
    "TOMADOR = quem contratou/pagou (CNPJ que voce vai extrair)\n\n"
    "Retorne exatamente neste formato:\n"
    '{"tipo":"NFSe","numero_documento":"123","eh_pedido":false,'
    '"fornecedor_curto":"NOME MAX 28 CHARS","cnpj_tomador":"00000000000000",'
    '"valor":0.00,"vencimento":"DD-MM","rotacao":0}\n\n'
    "rotacao: 0=normal, 180=cabeca pra baixo, 90=virado direita, 270=virado esquerda\n"
    "tipo pode ser: NFSe, NFe, fatura, recibo, DARF, outro"
)


@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response


@app.route("/health", methods=["GET", "OPTIONS"])
def health():
    return jsonify({"status": "ok", "message": "Servidor Di Gaspi rodando!"})


@app.route("/read-nf", methods=["POST", "OPTIONS"])
def read_nf():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    try:
        data = request.get_json()
        pdf_b64 = data.get("pdf_base64")
        if not pdf_b64:
            return jsonify({"error": "pdf_base64 e obrigatorio"}), 400

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
