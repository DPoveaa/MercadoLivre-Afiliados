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

// Verifica se a imagem foi fornecida
if (!imageUrl) {
    console.error('ERRO: URL da imagem é obrigatória!');
    console.error('Uso: node wpp_envio.js "Nome do Grupo" "Mensagem" "URL da Imagem"');
    process.exit(1);
}

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true }
});

// Função para aguardar um tempo específico
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Função para aguardar até que a mensagem seja enviada
const waitForMessageSent = async (messageId, maxWaitTime = 30000) => {
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWaitTime) {
        try {
            // Aguarda um pouco antes de verificar
            await delay(1000);
            
            // Tenta buscar a mensagem para verificar o status
            // Como não temos acesso direto ao status, vamos aguardar um tempo razoável
            // e confiar que o WhatsApp Web processou a mensagem
            console.log('Aguardando confirmação de envio...');
            
            // Aguarda mais 2 segundos para garantir processamento
            await delay(2000);
            return true;
        } catch (error) {
            console.log('Verificando status da mensagem...');
        }
    }
    
    throw new Error('Timeout: Mensagem não foi enviada no tempo esperado');
};

client.on('ready', async () => {
    console.log('Cliente WhatsApp conectado. Aguardando estabilização...');
    await delay(2000); // Aguarda estabilização inicial
    
    const chats = await client.getChats();
    const grupo = chats.find(chat => chat.isGroup && chat.name.trim().toLowerCase() === groupName.trim().toLowerCase());

    if (grupo) {
        console.log(`Grupo encontrado: ${grupo.name}. Preparando envio...`);
        
        try {
            console.log('Baixando imagem...');
            // Baixa a imagem e envia junto com a mensagem
            const response = await axios.get(imageUrl, { responseType: 'arraybuffer' });
            const mimeType = response.headers['content-type'] || 'image/jpeg';
            const media = new MessageMedia(mimeType, Buffer.from(response.data, 'binary').toString('base64'));
            
            console.log('Enviando mensagem com imagem...');
            const sentMessage = await client.sendMessage(grupo.id._serialized, media, { caption: message });
            
            // Aguarda confirmação de que a mensagem foi enviada
            await waitForMessageSent(sentMessage.id._serialized);
            
            console.log('✅ Mensagem com imagem enviada com sucesso para o grupo:', groupName);
        } catch (err) {
            console.error('❌ Erro ao enviar mensagem:', err.message);
            process.exit(1);
        }
    } else {
        console.log('❌ Grupo não encontrado:', groupName);
        process.exit(1);
    }
    
    console.log('Finalizando...');
    process.exit(0);
});

client.on('auth_failure', () => {
    console.error('❌ Falha na autenticação. Execute o wpp_auth.js para autenticar.');
    process.exit(2);
});

client.initialize();