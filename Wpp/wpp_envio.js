require('dotenv').config();
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const axios = require('axios');

// Recebe argumentos: node wpp_envio.js "Nome do Grupo" "Mensagem" ["URL da Imagem"]
const groupName = process.argv[2];
const message = process.argv[3];
const imageUrl = process.argv[4];

if (!groupName || !message) {
    console.error('Uso: node wpp_envio.js "Nome do Grupo" "Mensagem" ["URL da Imagem"]');
    process.exit(1);
}

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true }
});

client.on('ready', async () => {
    const chats = await client.getChats();
    const grupo = chats.find(chat => chat.isGroup && chat.name.trim().toLowerCase() === groupName.trim().toLowerCase());

    if (grupo) {
        if (imageUrl) {
            try {
                // Baixa a imagem e envia junto com a mensagem
                const response = await axios.get(imageUrl, { responseType: 'arraybuffer' });
                const mimeType = response.headers['content-type'] || 'image/jpeg';
                const media = new MessageMedia(mimeType, Buffer.from(response.data, 'binary').toString('base64'));
                await client.sendMessage(grupo.id._serialized, media, { caption: message });
                console.log('Mensagem com imagem enviada com sucesso para o grupo:', groupName);
            } catch (err) {
                console.error('Erro ao baixar ou enviar a imagem:', err);
                // Envia só o texto se a imagem falhar
                await client.sendMessage(grupo.id._serialized, message);
                console.log('Mensagem de texto enviada para o grupo:', groupName);
            }
        } else {
            await client.sendMessage(grupo.id._serialized, message);
            console.log('Mensagem enviada com sucesso para o grupo:', groupName);
        }
    } else {
        console.log('Grupo não encontrado:', groupName);
    }
    process.exit(0);
});

client.on('auth_failure', () => {
    console.error('Falha na autenticação. Execute o wpp_auth.js para autenticar.');
    process.exit(2);
});

client.initialize();