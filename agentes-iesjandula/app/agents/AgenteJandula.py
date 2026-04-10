from .AgentConfig import configurar_grafo_ies
from .abilities.Audio import MotorVoz

class AgenteJandula:
    def __init__(self, perfil: str, modo: str):
        self.perfil = perfil 
        self.modo = modo     
        self.grafo = None
        self.motor_voz = None

    async def encender(self):
        self.grafo = await configurar_grafo_ies(self.perfil, es_voz=(self.modo == "voz"))
        if self.modo in ["voz", "hibrido"]:
            self.motor_voz = MotorVoz()

    async def responder(self, entrada, thread_id="default"):
        texto_usuario = entrada
        if self.modo in ["voz", "hibrido"]:
            texto_usuario = self.motor_voz.escuchar(entrada)

        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 15}
        resultado = await self.grafo.ainvoke({"messages": [("user", texto_usuario)]}, config)
        respuesta_texto = resultado["messages"][-1].content

        if self.modo == "voz":
            return self.motor_voz.hablar(respuesta_texto)
        
        if self.modo == "hibrido":
            return {"transcripcion": texto_usuario, "respuesta": respuesta_texto}
        
        print(f"🤖 Respuesta enviada ({len(respuesta_texto)} caracteres)")
        return respuesta_texto