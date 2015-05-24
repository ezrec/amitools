from amitools.vamos.AmigaLibrary import *
from lexec.ExecStruct import *
from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *
from amitools.vamos.AccessStruct import AccessStruct

NT_SIGNALSEM = 15
NT_LIBRARY = 9

class ExecLibrary(AmigaLibrary):
  name = "exec.library"

  def __init__(self, lib_mgr, alloc, config):
    AmigaLibrary.__init__(self, self.name, ExecLibraryDef, config)
    log_exec.info("open exec.library V%d", self.version)
    self.lib_mgr = lib_mgr
    self.alloc = alloc
    
  def set_this_task(self, process):
    self.access.w_s("ThisTask",process.this_task.addr)
    self.stk_lower = process.stack_base
    self.stk_upper = process.stack_end
  
  def set_cpu(self, cpu):
    if cpu == '68020':
      self.access.w_s("AttnFlags",2)
    else:
      self.access.w_s("AttnFlags",0)
  
  def set_ram_size(self, mem_size):
    self.access.w_s("MaxLocMem", mem_size)

  # ----- System -----
  
  def Disable(self, ctx):
    log_exec.info("Disable")
  def Enable(self, ctx):
    log_exec.info("Enable")
  def Forbid(self, ctx):
    log_exec.info("Forbid")
  def Permit(self, ctx):
    log_exec.info("Permit")
    
  def FindTask(self, ctx):
    task_ptr = ctx.cpu.r_reg(REG_A1)
    if task_ptr == 0:
      addr = self.access.r_s("ThisTask")
      log_exec.info("FindTask: me=%06x" % addr)
      return addr
    else:
      task_name = ctx.mem.access.r_cstr(task_ptr)
      log_exec.info("Find Task: %s" % task_name)
      raise UnsupportedFeatureError("FindTask: other task!");
  
  def SetSignal(self, ctx):
    new_signals = ctx.cpu.r_reg(REG_D0)
    signal_mask = ctx.cpu.r_reg(REG_D1)
    old_signals = 0
    log_exec.info("SetSignals: new_signals=%08x signal_mask=%08x old_signals=%08x" % (new_signals, signal_mask, old_signals))
    return old_signals
  
  def StackSwap(self, ctx):
    stsw_ptr = ctx.cpu.r_reg(REG_A0)
    stsw = AccessStruct(ctx.mem,StackSwapDef,struct_addr=stsw_ptr)
    # get new stack values
    new_lower = stsw.r_s('stk_Lower')
    new_upper = stsw.r_s('stk_Upper')
    new_pointer = stsw.r_s('stk_Pointer')
    # retrieve current (old) stack
    old_lower = self.stk_lower
    old_upper = self.stk_upper
    old_pointer = ctx.cpu.r_reg(REG_A7) # addr of sys call return
    # get adress of callee
    callee = ctx.mem.access.r32(old_pointer)
    # is a label attached to new addr
    label = ctx.label_mgr.get_label(new_lower)
    if label is not None:
      label.name = label.name + "=Stack"
    # we report the old stack befor callee
    old_pointer += 4
    log_exec.info("StackSwap: old(lower=%06x,upper=%06x,ptr=%06x) new(lower=%06x,upper=%06x,ptr=%06x)" % (old_lower,old_upper,old_pointer,new_lower,new_upper,new_pointer))
    stsw.w_s('stk_Lower', old_lower)
    stsw.w_s('stk_Upper', old_upper)
    stsw.w_s('stk_Pointer', old_pointer)
    self.stk_lower = new_lower
    self.stk_upper = new_upper
    # put callee's address on new stack
    new_pointer -= 4
    ctx.mem.access.w32(new_pointer,callee)
    # activate new stack
    ctx.cpu.w_reg(REG_A7, new_pointer)
    
  # ----- Libraries -----
  
  def InitStruct(self, ctx):
    table_ptr = ctx.cpu.r_reg(REG_A1)
    struct_ptr = ctx.cpu.r_reg(REG_A2)
    size = ctx.cpu.r_reg(REG_D0)
    size &= 0xffff
    log_exec.info("InitStruct(table=%06x, struct=%06x, size=%d)", table_ptr, struct_ptr, size)
    ctx.mem.access.clear_mem(struct_ptr, size, 0)
    op = ctx.mem.access.r8(table_ptr)
    dest_ptr = struct_ptr
    while op != 0:
      ty = (op >> 6) & 0x3
      sz = (op >> 4) & 0x3
      cnt = (op >> 0) & 0xf
      log_exec.info(" ty=%d, sz=%d, cnt=%d", ty, sz, cnt)

      # Skip the action byte
      table_ptr = table_ptr + 1

      if ty == 0 or ty == 1:
        # No more information
        off = 0
      elif ty == 2:
        # Skip the action byte, get the offset
        off = ctx.mem.access.r8(table_ptr)
      elif ty == 3:
        off = (ctx.mem.access.r8(table_ptr) << 16) | ctx.mem.access.r8(table_ptr + 1)
        table_ptr = table_ptr + 3
      
      if sz == 0:
        # Align to long
        al = 4
      elif sz == 1:
        al = 2
      elif sz == 2:
        al = 1
      elif sz == 3:
        al = 8

      table_ptr  = (table_ptr + (al - 1)) & ~(al - 1)
      dest_ptr   = (dest_ptr  + (al - 1)) & ~(al - 1)

      if ty == 2 or ty == 3:
        # Add offset then copy
        dest_ptr = struct_ptr + off
      
      if ty == 0 or ty == 2 or ty == 3:
        if sz == 0:
          while cnt > 0:
            tmp = ctx.mem.access.r32(table_ptr)
            ctx.mem.access.w32(dest_ptr, tmp)
            dest_ptr = dest_ptr + 4
            table_ptr = table_ptr + 4
            cnt = cnt - 1
        elif sz == 1:
          while cnt > 0:
            tmp = ctx.mem.access.r16(table_ptr)
            ctx.mem.access.w16(dest_ptr, tmp)
            dest_ptr = dest_ptr + 2
            table_ptr = table_ptr + 2
            cnt = cnt - 1
        elif sz == 2:
          while cnt > 0:
            tmp = ctx.mem.access.r8(table_ptr)
            ctx.mem.access.w8(dest_ptr, tmp)
            dest_ptr = dest_ptr + 1
            table_ptr = table_ptr + 1
            cnt = cnt - 1
        elif sz == 3:
          while cnt > 0:
            tmp = ctx.mem.access.r64(table_ptr)
            ctx.mem.access.w64(dest_ptr, tmp)
            dest_ptr = dest_ptr + 8
            table_ptr = table_ptr + 8
            cnt = cnt - 1
      elif ty == 1:
        # Action: Repeat element
        if sz == 0:
          tmp = ctx.mem.access.r32(table_ptr)
          while cnt > 0:
            ctx.mem.access.w32(dest_ptr, tmp)
            dest_ptr = dest_ptr + 4
            cnt = cnt - 1
        elif sz == 1:
          tmp = ctx.mem.access.r16(table_ptr)
          while cnt > 0:
            ctx.mem.access.w16(dest_ptr, tmp)
            dest_ptr = dest_ptr + 2
            cnt = cnt - 1
        elif sz == 2:
          tmp = ctx.mem.access.r8(table_ptr)
          while cnt > 0:
            ctx.mem.access.w8(dest_ptr, tmp)
            dest_ptr = dest_ptr + 1
            cnt = cnt - 1
        elif sz == 3:
          tmp = ctx.mem.access.r64(table_ptr)
          while cnt > 0:
            ctx.mem.access.w64(dest_ptr, tmp)
            dest_ptr = dest_ptr + 8
            cnt = cnt - 1
      table_ptr = (table_ptr + (4 - 1)) & ~(4 - 1)
      op = ctx.mem.access.r8(table_ptr)
    
  def MakeFunctions(self, ctx):
    target_ptr = ctx.cpu.r_reg(REG_A0)
    fnarr_ptr  = ctx.cpu.r_reg(REG_A1)
    fnbase_ptr = ctx.cpu.r_reg(REG_A2)
    n = 1
    if fnbase_ptr != 0:
      fp = fnbase_ptr
      fd = ctx.mem.access.r16(fp)
      while fd != 0xffff:
        vec_ptr = target_ptr - (n * 4)
        ctx.mem.access.w16(vec_ptr, 0x4EF9)
        ctx.mem.access.w32(vec_ptr + 2, fnbase_ptr + fd)
        fp = fp + 2
        fd = ctx.mem.access.r16(fp)
        n = n + 1
    else:
      fa = fnarr_ptr
      fn = ctx.cpu.r32(fa)
      while fn != 0xffffffff:
        vec_ptr = target_ptr - (n * 4)
        ctx.mem.access.w16(vec_ptr, 0x4EF9)
        ctx.mem.access.w32(vec_ptr + 2, fn)
        fa = fa + 4
        fn = ctx.mem.access.r32(fa)
        n = n + 1
    n = n - 1
    log_exec.info("MakeFunctions(target=%06x, fnarr=%06x, fnbase=%06x) => %d", target_ptr, fnarr_ptr, fnbase_ptr, n)
    return n

  def AddLibrary(self, ctx):
    lib_ptr = ctx.cpu.r_reg(REG_A1)
    lib = AccessStruct(ctx.mem, LibraryDef, lib_ptr)
    # Set up lib_Node
    lib.w_s("lib_Node.ln_Succ", lib_ptr)
    lib.w_s("lib_Node.ln_Pred", lib_ptr)
    lib.w_s("lib_Node.ln_Type", NT_LIBRARY)
    return lib_ptr
  
  def OpenLibrary(self, ctx):
    ver = ctx.cpu.r_reg(REG_D0)
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lib = self.lib_mgr.open_lib(name, ver, ctx)
    log_exec.info("OpenLibrary: '%s' V%d -> %s" % (name, ver, lib))
    if lib == None:
      return 0
    else:
      return lib.addr_base_open
  
  def OldOpenLibrary(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lib = self.lib_mgr.open_lib(name, 0, ctx)
    log_exec.info("OldOpenLibrary: '%s' -> %s" % (name, lib))
    return lib.addr_base_open
  
  def CloseLibrary(self, ctx):
    lib_addr = ctx.cpu.r_reg(REG_A1)
    lib = self.lib_mgr.close_lib(lib_addr,ctx)
    if lib != None:
      log_exec.info("CloseLibrary: '%s' -> %06x" % (lib, lib.addr_base))
    else:
      raise VamosInternalError("CloseLibrary: Unknown library to close: ptr=%06x" % lib_addr)
  
  def FindResident(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    log_exec.info("FindResident: '%s'" % (name))
    return 0

  # ----- Memory Handling -----
  
  def AllocMem(self, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    flags = ctx.cpu.r_reg(REG_D1)
    # label alloc
    pc = self.get_callee_pc(ctx)
    tag = ctx.label_mgr.get_mem_str(pc)
    name = "AllocMem(%06x = %s)" % (pc,tag)
    mb = self.alloc.alloc_memory(name,size)
    log_exec.info("AllocMem: %s" % mb)
    return mb.addr
  
  def FreeMem(self, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    addr = ctx.cpu.r_reg(REG_A1)
    if addr == 0 or size == 0:
      log_exec.info("FreeMem: freeing NULL")
      return
    mb = self.alloc.get_memory(addr)
    if mb != None:
      log_exec.info("FreeMem: %s" % mb)
      self.alloc.free_memory(mb)
    else:
      raise VamosInternalError("FreeMem: Unknown memory to free: ptr=%06x size=%06x" % (addr, size))

  def AllocVec(self, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    flags = ctx.cpu.r_reg(REG_D1)
    mb = self.alloc.alloc_memory("AllocVec(@%06x)" % self.get_callee_pc(ctx),size)
    log_exec.info("AllocVec: %s" % mb)
    return mb.addr
    
  def FreeVec(self, ctx):
    addr = ctx.cpu.r_reg(REG_A1)
    if addr == 0:
      log_exec.info("FreeVec: freeing NULL")
      return
    mb = self.alloc.get_memory(addr)
    if mb != None:
      log_exec.info("FreeVec: %s" % mb)
      self.alloc.free_memory(mb)
    else:
      raise VamosInternalError("FreeVec: Unknown memory to free: ptr=%06x" % (addr))
  
  # ----- Misc -----
  
  def RawDoFmt(self, ctx):
    format_ptr = ctx.cpu.r_reg(REG_A0)
    format     = ctx.mem.access.r_cstr(format_ptr)
    data_ptr   = ctx.cpu.r_reg(REG_A1)
    putch_ptr  = ctx.cpu.r_reg(REG_A2)
    pdata_ptr  = ctx.cpu.r_reg(REG_A3)
    log_exec.info("RawDoFmt: format='%s' data=%06x putch=%06x pdata=%06x" % (format, data_ptr, putch_ptr, pdata_ptr))
  
  # ----- Message Passing -----
  
  def PutMsg(self, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    msg_addr = ctx.cpu.r_reg(REG_A1)
    log_exec.info("PutMsg: port=%06x msg=%06x" % (port_addr, msg_addr))
    has_port = ctx.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("PutMsg: on invalid Port (%06x) called!" % port_addr)
    ctx.port_mgr.put_msg(port_addr, msg_addr)
      
  def GetMsg(self, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    log_exec.info("GetMsg: port=%06x" % (port_addr))
    has_port = ctx.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("GetMsg: on invalid Port (%06x) called!" % port_addr)
    msg_addr = ctx.port_mgr.get_msg(port_addr)
    if msg_addr != None:
      log_exec.info("GetMsg: got message %06x" % (msg_addr))
      return msg_addr
    else:
      log_exec.info("GetMsg: no message available!")
      return 0
  
  def WaitPort(self, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    log_exec.info("WaitPort: port=%06x" % (port_addr))
    has_port = ctx.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("WaitPort: on invalid Port (%06x) called!" % port_addr)
    has_msg = ctx.port_mgr.has_msg(port_addr)
    if not has_msg:
      raise UnsupportedFeatureError("WaitPort on empty message queue called: Port (%06x)" % port_addr)
    msg_addr = ctx.port_mgr.get_msg(port_addr)
    log_exec.info("WaitPort: got message %06x" % (msg_addr))
    return msg_addr

  def AddTail(self, ctx):
    list_addr = ctx.cpu.r_reg(REG_A0)
    node_addr = ctx.cpu.r_reg(REG_A1)
    log_exec.info("AddTail(%06x, %06x)" % (list_addr, node_addr))
    l = AccessStruct(ctx.mem, ListDef, list_addr)
    n = AccessStruct(ctx.mem, NodeDef, node_addr)
    n.w_s("ln_Succ", l.s_get_addr("lh_Tail"))
    tp = l.r_s("lh_TailPred")
    n.w_s("ln_Pred", tp)
    AccessStruct(ctx.mem, NodeDef, tp).w_s("ln_Succ", node_addr)
    l.w_s("lh_TailPred", node_addr)

  def Remove(self, ctx):
    node_addr = ctx.cpu.r_reg(REG_A1)
    n = AccessStruct(ctx.mem, NodeDef, node_addr)
    succ = n.r_s("ln_Succ")
    pred = n.r_s("ln_Pred")
    log_exec.info("Remove(%06x): ln_Pred=%06x ln_Succ=%06x" % (node_addr, pred, succ))
    AccessStruct(ctx.mem, NodeDef, pred).w_s("ln_Succ", succ)
    AccessStruct(ctx.mem, NodeDef, succ).w_s("ln_Pred", pred)
    return node_addr

  # ----- Semaphores -----
  
  def InitSemaphore(self, ctx):
    sem_addr = ctx.cpu.r_reg(REG_A0)
    sem = AccessStruct(ctx.mem, SignalSemaphoreDef, sem_addr)
    log_exec.info("InitSemaphore(%06x)", sem_addr)
    wq_tail_ptr = sem.r_s("ss_WaitQueue.mlh_Tail")
    wq_head_ptr = sem.r_s("ss_WaitQueue.mlh_Head")
    sem.w_s("ss_WaitQueue.mlh_Head", wq_tail_ptr)
    sem.w_s("ss_WaitQueue.mlh_Tail", 0)
    sem.w_s("ss_WaitQueue.mlh_TailPred", wq_head_ptr)
    sem.w_s("ss_Link.ln_Type", NT_SIGNALSEM)
    sem.w_s("ss_NestCount", 0)
    sem.w_s("ss_Owner", 0)
    sem.w_s("ss_QueueCount", -1)


