// One current AI operation. Results are bound to the complete submitted input.
export class AISession {
  constructor(){this.revision=0;this.controller=null;this.active=null;}
  start(body){this.cancel();this.controller=new AbortController();this.active={revision:this.revision,fingerprint:JSON.stringify(body)};return {...this.active,signal:this.controller.signal};}
  current(ticket,body){return ticket.revision===this.revision&&ticket.fingerprint===JSON.stringify(body);}
  cancel(){this.revision++;this.controller?.abort();this.controller=null;this.active=null;}
}
