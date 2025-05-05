const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const fetch = require('node-fetch').default;
const mime = require('mime-types');

const [,, legenda, nomeGrupo, imageUrl] = process.argv;

console.log('[INFO] Iniciando cliente WhatsApp...');
console.log('[INFO] Grupo alvo:', nomeGrupo);
console.log('[INFO] Imagem URL:', imageUrl || 'Nenhuma imagem');

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './auth_data' }),
    puppeteer: {
        headless: true,  // Mude para true em produção
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage', // Adicione isso para evitar problemas de memória
            '--single-process' // Pode ajudar em ambientes com recursos limitados
        ],
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined // Útil para Docker
    },
    restartOnAuthFail: true,
    takeoverOnConflict: true,
    takeoverTimeoutMs: 5000
});

// Adicione mais listeners para debug
client.on('loading_screen', (percent, message) => {
    console.log(`[LOADING] ${percent}%: ${message}`);
});

client.on('qr', qr => {
    console.log('[QR] Scan this QR to authenticate');
});

client.on('disconnected', (reason) => {
    console.log('[DISCONNECTED]', reason);
});

client.on('authenticated', () => {
    console.log('[AUTH] Autenticado com sucesso');
});

client.on('auth_failure', msg => {
    console.error('[AUTH ERROR]', msg);
    process.exit(1);
});

client.on('ready', async () => {
    try {
        console.log('[READY] Cliente pronto! Aguardando sincronização...');
        
        // Aumente o tempo de espera para 10 segundos
        await new Promise(resolve => setTimeout(resolve, 10000));

        console.log('[INFO] Buscando chats...');
        const chats = await client.getChats();
        console.log(`[INFO] Encontrados ${chats.length} chats`);

        const grupo = chats.find(chat =>
            chat.isGroup &&
            chat.name.toLowerCase().trim() === nomeGrupo.toLowerCase().trim()
        );

        if (!grupo) {
            console.error(`[ERROR] Grupo "${nomeGrupo}" não encontrado. Chats disponíveis:`);
            chats.filter(c => c.isGroup).forEach(c => console.log(`- ${c.name}`));
            throw new Error(`Grupo "${nomeGrupo}" não encontrado`);
        }

        console.log(`[INFO] Enviando para grupo: ${grupo.name}`);
        const chat = await client.getChatById(grupo.id._serialized);

        if (imageUrl && imageUrl.trim() !== '') {
            try {
                console.log('[INFO] Baixando imagem...');
                const res = await fetch(imageUrl, { timeout: 10000 });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);

                console.log('[INFO] Convertendo imagem...');
                const buffer = await res.buffer();
                const media = new MessageMedia(
                    res.headers.get('content-type') || mime.lookup(imageUrl) || 'image/jpeg',
                    buffer.toString('base64'),
                    'promocao.jpg'
                );

                console.log('[INFO] Enviando mensagem com imagem...');
                await chat.sendMessage(media, { caption: legenda });
            } catch (imgErr) {
                console.error('[ERROR] Erro ao enviar imagem:', imgErr.message);
                console.log('[INFO] Enviando apenas texto como fallback...');
                await chat.sendMessage(legenda);
            }
        } else {
            console.log('[INFO] Enviando apenas texto...');
            await chat.sendMessage(legenda);
        }

        console.log('[SUCCESS] Mensagem enviada com sucesso!');
    } catch (error) {
        console.error('[ERROR] Erro no processo:', error);
    } finally {
        console.log('[INFO] Encerrando cliente...');
        try {
            await client.destroy();
            console.log("[SUCCESS] Cliente encerrado com sucesso.");
            process.exit(0); // Saída explícita com código de sucesso
        } catch (e) {
            console.error("[ERROR] Erro ao encerrar o cliente:", e);
            process.exit(1);
        }
    }
});

// Melhore os handlers de erro
process.on('uncaughtException', (err) => {
    console.error('❌ Uncaught Exception:', err);
    client.destroy().then(() => process.exit(1));
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('❌ Unhandled Rejection:', reason);
    client.destroy().then(() => process.exit(1));
});

client.initialize().catch(err => {
    console.error('[ERROR] Falha ao inicializar:', err);
    process.exit(1);
});