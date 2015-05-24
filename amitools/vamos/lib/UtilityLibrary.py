from amitools.vamos.AmigaLibrary import *
from amitools.vamos.lib.lexec.ExecStruct import LibraryDef
from amitools.vamos.Log import *

from util.TagList import *

class UtilityLibrary(AmigaLibrary):
  name = "utility.library"
  
  def __init__(self, config):
    AmigaLibrary.__init__(self, self.name, LibraryDef, config)

  def UDivMod32(self, ctx):
    dividend = ctx.cpu.r_reg(REG_D0)
    divisor = ctx.cpu.r_reg(REG_D1)
    quot = dividend / divisor
    rem  = dividend % divisor
    log_utility.info("UDivMod32(dividend=%u, divisor=%u) => (quotient=%u, remainder=%u)" % (dividend, divisor, quot, rem))
    return [quot, rem]

  def UMult32(self, ctx):
    a = ctx.cpu.r_reg(REG_D0)
    b = ctx.cpu.r_reg(REG_D1)
    c = (a * b) & 0xffffffff
    log_utility.info("UMult32(a=%u, b=%u) => %u", a, b, c)
    return c

  def GetTagData(self, ctx):
    tagValue = ctx.cpu.r_reg(REG_D0)
    defValue = ctx.cpu.r_reg(REG_D1)
    tagList  = ctx.cpu.r_reg(REG_A0)
    rc = taglist_find_tagitem(ctx.mem, tagList, tagValue, defValue)
    log_utility.info("GetTagData(tagValue=0x%08x, defValue=%d, tagList=%06x) => %d" % (tagValue, defValue, tagList, rc))
    return rc
