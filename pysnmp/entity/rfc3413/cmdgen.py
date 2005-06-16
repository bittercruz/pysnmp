import types, time
from pysnmp.proto import rfc1157, rfc1905, api
from pysnmp.smi import view
from pysnmp.proto import error

def getVersionSpecifics(snmpVersion):
    if snmpVersion < 3:
        pduVersion = snmpVersion
    else:
        pduVersion = 1
    return pduVersion, api.protoModules[pduVersion]

def getTargetInfo(snmpEngine, snmpTargetAddrName):
    mibInstrumController = snmpEngine.msgAndPduDsp.mibInstrumController
    # Transport endpoint
    snmpTargetAddrEntry, = mibInstrumController.mibBuilder.importSymbols(
        'SNMP-TARGET-MIB', 'snmpTargetAddrEntry'
        )
    tblIdx = snmpTargetAddrEntry.getInstIdFromIndices(
        snmpTargetAddrName
        )
    snmpTargetAddrTDomain = snmpTargetAddrEntry.getNode(
        snmpTargetAddrEntry.name + (2,) + tblIdx
        )
    snmpTargetAddrTAddress = snmpTargetAddrEntry.getNode(
        snmpTargetAddrEntry.name + (3,) + tblIdx
        )
    snmpTargetAddrTimeout = snmpTargetAddrEntry.getNode(
        snmpTargetAddrEntry.name + (4,) + tblIdx
        )
    snmpTargetAddrRetryCount = snmpTargetAddrEntry.getNode(
        snmpTargetAddrEntry.name + (5,) + tblIdx
        )
    snmpTargetAddrParams = snmpTargetAddrEntry.getNode(
        snmpTargetAddrEntry.name + (7,) + tblIdx
        )
    
    # Target params
    snmpTargetParamsEntry, = mibInstrumController.mibBuilder.importSymbols(
        'SNMP-TARGET-MIB', 'snmpTargetParamsEntry'
        )
    tblIdx = snmpTargetParamsEntry.getInstIdFromIndices(
        snmpTargetAddrParams.syntax
        )
    snmpTargetParamsMPModel = snmpTargetParamsEntry.getNode(
        snmpTargetParamsEntry.name + (2,) + tblIdx
        )
    snmpTargetParamsSecurityModel = snmpTargetParamsEntry.getNode(
        snmpTargetParamsEntry.name + (3,) + tblIdx
        )
    snmpTargetParamsSecurityName = snmpTargetParamsEntry.getNode(
        snmpTargetParamsEntry.name + (4,) + tblIdx
        )
    snmpTargetParamsSecurityLevel = snmpTargetParamsEntry.getNode(
        snmpTargetParamsEntry.name + (5,) + tblIdx
        )

    return ( tuple(snmpTargetAddrTDomain.syntax),
             snmpTargetAddrTAddress.syntax.getNativeValue(),
             snmpTargetAddrTimeout.syntax,
             snmpTargetAddrRetryCount.syntax,
             snmpTargetParamsMPModel.syntax,
             snmpTargetParamsSecurityModel.syntax,
             snmpTargetParamsSecurityName.syntax,
             snmpTargetParamsSecurityLevel.syntax )

class CmdGenBase:
    def __init__(self):
        self.__pendingReqs = {}
        self._sendRequestHandleSource = 0L
            
    def processResponsePdu(
        self,
        snmpEngine,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineID,
        contextName,
        pduVersion,
        PDU,
        statusInformation,
        sendPduHandle,
        (cbFun, cbCtx)
        ):
        # 3.1.1
        ( origTransportDomain,
          origTransportAddress,
          origMessageProcessingModel,
          origSecurityModel,
          origSecurityName,
          origSecurityLevel,
          origContextEngineID,
          origContextName,
          origPduVersion,
          origPdu,
          origTimeout,
          origRetryCount,
          origRetries,
          origSendRequestHandle
          ) = self.__pendingReqs[sendPduHandle]
        del self.__pendingReqs[sendPduHandle]

        # 3.1.3
        if statusInformation: # and statusInformation.has_key('errorIndication'):
            if origRetries == origRetryCount:
                cbFun(origSendRequestHandle,
                      statusInformation['errorIndication'], 0, 0, (),
                      cbCtx)
                return
            self._sendPdu(
                snmpEngine,
                origTransportDomain,
                origTransportAddress,
                origMessageProcessingModel,
                origSecurityModel,
                origSecurityName,
                origSecurityLevel,
                origContextEngineID,
                origContextName,
                origPduVersion,
                origPdu,
                origTimeout,
                origRetryCount,
                origRetries,
                origSendRequestHandle,
                (self.processResponsePdu, (cbFun, cbCtx))
                )
            return
        
        if origMessageProcessingModel != messageProcessingModel or \
           origSecurityModel != securityModel or \
           origSecurityName != origSecurityName or \
           origContextEngineID and origContextEngineID != contextEngineID or \
           origContextName and origContextName != contextName or \
           origPduVersion != pduVersion:
            return

        pMod = api.protoModules[pduVersion]
        
        # 3.1.2
        if pMod.apiPDU.getRequestID(PDU) != pMod.apiPDU.getRequestID(origPdu):
            return

        self._handleResponse(
            snmpEngine,
            origTransportDomain,
            origTransportAddress,
            origMessageProcessingModel,
            origSecurityModel,
            origSecurityName,
            origSecurityLevel,
            origContextEngineID,
            origContextName,
            origPduVersion,
            origPdu,
            origTimeout,
            origRetryCount,
            pMod,
            PDU,
            origSendRequestHandle,
            (cbFun, cbCtx),
            )
        
    def sendReq(
        self,
        snmpEngine,
        addrName,
        varBinds,
        cbFun,
        cbCtx=None,
        contextEngineID=None,
        contextName=''
        ):
        raise error.ProtocolError('Method not implemented')

    def _sendPdu(
        self,
        snmpEngine,
        transportDomain,
        transportAddress,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineID,
        contextName,
        pduVersion,
        reqPDU,
        timeout,
        retryCount,
        retries,
        sendRequestHandle,
        (processResponsePdu, cbCtx)
        ):    
        # 3.1
        sendPduHandle = snmpEngine.msgAndPduDsp.sendPdu(
            snmpEngine,
            transportDomain,
            transportAddress,
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineID,
            contextName,
            pduVersion,
            reqPDU,
            (processResponsePdu, timeout/1000 + time.time(), cbCtx)
            )

        self.__pendingReqs[sendPduHandle] = (
            transportDomain,
            transportAddress,
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineID,
            contextName,
            pduVersion,
            reqPDU,
            timeout,
            retryCount,
            retries + 1,
            sendRequestHandle,
            )

class SnmpGet(CmdGenBase):
    def sendReq(
        self,
        snmpEngine,
        addrName,
        varBinds,
        cbFun,
        cbCtx=None,
        contextEngineID=None,
        contextName=''
        ):
        ( transportDomain,
          transportAddress,
          timeout,
          retryCount,
          messageProcessingModel,
          securityModel,
          securityName,
          securityLevel ) = getTargetInfo(snmpEngine, addrName)

        pduVersion, pMod = getVersionSpecifics(messageProcessingModel)
        
        reqPDU = pMod.GetRequestPDU()
        pMod.apiPDU.setDefaults(reqPDU)
        
        pMod.apiPDU.setVarBinds(reqPDU, varBinds)

        self._sendRequestHandleSource = self._sendRequestHandleSource + 1
        
        self._sendPdu(
            snmpEngine,
            transportDomain,
            transportAddress,
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineID,
            contextName,
            pduVersion,
            reqPDU,
            timeout,
            retryCount,
            0,
            self._sendRequestHandleSource,
            (self.processResponsePdu, (cbFun, cbCtx))            
            )
        
        return self._sendRequestHandleSource
    
    def _handleResponse(
        self,
        snmpEngine,
        transportDomain,
        transportAddress,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineID,
        contextName,
        pduVersion,
        PDU,
        timeout,
        retryCount,
        pMod,
        rspPDU,
        sendRequestHandle,
        (cbFun, cbCtx)
        ):
        cbFun(sendRequestHandle,
              None,
              pMod.apiPDU.getErrorStatus(rspPDU),
              pMod.apiPDU.getErrorIndex(rspPDU),
              pMod.apiPDU.getVarBinds(rspPDU),
              cbCtx)

class SnmpSet(CmdGenBase):
    def sendReq(
        self,
        snmpEngine,
        addrName,
        varBinds,
        cbFun,
        cbCtx=None,
        contextEngineID=None,
        contextName=''
        ):
        ( transportDomain,
          transportAddress,
          timeout,
          retryCount,
          messageProcessingModel,
          securityModel,
          securityName,
          securityLevel ) = getTargetInfo(snmpEngine, addrName)

        pduVersion, pMod = getVersionSpecifics(messageProcessingModel)
        
        reqPDU = pMod.SetRequestPDU()
        pMod.apiPDU.setDefaults(reqPDU)

        pMod.apiPDU.setVarBinds(reqPDU, varBinds)
        
        self._sendRequestHandleSource = self._sendRequestHandleSource + 1
        
        self._sendPdu(
            snmpEngine,
            transportDomain,
            transportAddress,
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineID,
            contextName,
            pduVersion,
            reqPDU,
            timeout,
            retryCount,
            0,
            self._sendRequestHandleSource,
            (self.processResponsePdu, (cbFun, cbCtx))            
            )

        return self._sendRequestHandleSource

    def _handleResponse(
        self,
        snmpEngine,
        transportDomain,
        transportAddress,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineID,
        contextName,
        pduVersion,
        PDU,
        timeout,
        retryCount,
        pMod,
        rspPDU,
        sendRequestHandle,
        (cbFun, cbCtx)
        ):
        cbFun(sendRequestHandle,
              None,
              pMod.apiPDU.getErrorStatus(rspPDU),
              pMod.apiPDU.getErrorIndex(rspPDU),
              pMod.apiPDU.getVarBinds(rspPDU),
              cbCtx)

class SnmpWalk(CmdGenBase):
    def sendReq(
        self,
        snmpEngine,
        addrName,
        varBinds,
        cbFun,
        cbCtx=None,
        contextEngineID=None,
        contextName=''
        ):
        ( transportDomain,
          transportAddress,
          timeout,
          retryCount,
          messageProcessingModel,
          securityModel,
          securityName,
          securityLevel ) = getTargetInfo(snmpEngine, addrName)

        pduVersion, pMod = getVersionSpecifics(messageProcessingModel)
        
        reqPDU = pMod.GetNextRequestPDU()
        pMod.apiPDU.setDefaults(reqPDU)
        
        pMod.apiPDU.setVarBinds(reqPDU, varBinds)

        self._sendRequestHandleSource = self._sendRequestHandleSource + 1
        
        self._sendPdu(
            snmpEngine,
            transportDomain,
            transportAddress,
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineID,
            contextName,
            pduVersion,
            reqPDU,
            timeout,
            retryCount,
            0,
            self._sendRequestHandleSource,
            (self.processResponsePdu, (cbFun, cbCtx))            
            )

        return self._sendRequestHandleSource
    
    def _handleResponse(
        self,
        snmpEngine,
        transportDomain,
        transportAddress,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineID,
        contextName,
        pduVersion,
        PDU,
        timeout,
        retryCount,
        pMod,
        rspPDU,
        sendRequestHandle,
        (cbFun, cbCtx)
        ):
        varBindTable = pMod.apiPDU.getVarBindTable(PDU, rspPDU)
            
        cbFun(sendRequestHandle, None,
              pMod.apiPDU.getErrorStatus(rspPDU),
              pMod.apiPDU.getErrorIndex(rspPDU),
              varBindTable, cbCtx)
        
        pMod.apiPDU.setVarBinds(
            PDU, map(lambda (x,y),n=pMod.Null(): (x,n), varBindTable[-1])
            )

        self._sendRequestHandleSource = self._sendRequestHandleSource + 1
        
        self._sendPdu(
            snmpEngine,
            transportDomain,
            transportAddress,
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineID,
            contextName,
            pduVersion,
            PDU,
            timeout,
            retryCount,
            0,
            self._sendRequestHandleSource,
            (self.processResponsePdu, (cbFun, cbCtx))            
            )

class SnmpBulkWalk(CmdGenBase):
    def sendReq(
        self,
        snmpEngine,
        addrName,
        nonRepeaters,
        maxRepetitions,
        varBinds,
        cbFun,
        cbCtx=None,
        contextEngineID=None,
        contextName=''
        ):
        ( transportDomain,
          transportAddress,
          timeout,
          retryCount,
          messageProcessingModel,
          securityModel,
          securityName,
          securityLevel ) = getTargetInfo(snmpEngine, addrName)

        pduVersion, pMod = getVersionSpecifics(messageProcessingModel)
        
        reqPDU = pMod.GetBulkRequestPDU()
        
        pMod.apiBulkPDU.setNonRepeaters(reqPDU, nonRepeaters)
        pMod.apiBulkPDU.setMaxRepetitions(reqPDU, maxRepetitions)
        
        pMod.apiBulkPDU.setDefaults(reqPDU)
        
        pMod.apiBulkPDU.setVarBinds(reqPDU, varBinds)

        self._sendRequestHandleSource = self._sendRequestHandleSource + 1
        
        self._sendPdu(
            snmpEngine,
            transportDomain,
            transportAddress,
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineID,
            contextName,
            pduVersion,
            reqPDU,
            timeout,
            retryCount,
            0,
            self._sendRequestHandleSource,
            (self.processResponsePdu, (cbFun, cbCtx))            
            )

        return self._sendRequestHandleSource
    
    def _handleResponse(
        self,
        snmpEngine,
        transportDomain,
        transportAddress,
        messageProcessingModel,
        securityModel,
        securityName,
        securityLevel,
        contextEngineID,
        contextName,
        pduVersion,
        PDU,
        timeout,
        retryCount,
        pMod,
        rspPDU,
        sendRequestHandle,
        (cbFun, cbCtx)
        ):
        varBindTable = pMod.apiBulkPDU.getVarBindTable(PDU, rspPDU)
            
        cbFun(sendRequestHandle, None,
              pMod.apiBulkPDU.getErrorStatus(rspPDU),
              pMod.apiBulkPDU.getErrorIndex(rspPDU),
              varBindTable, cbCtx)
        
        pMod.apiBulkPDU.setVarBinds(
            PDU, map(lambda (x,y),n=pMod.Null(): (x,n), varBindTable[-1])
            )

        self._sendRequestHandleSource = self._sendRequestHandleSource + 1
        
        self._sendPdu(
            snmpEngine,
            transportDomain,
            transportAddress,
            messageProcessingModel,
            securityModel,
            securityName,
            securityLevel,
            contextEngineID,
            contextName,
            pduVersion,
            PDU,
            timeout,
            retryCount,
            0,
            self._sendRequestHandleSource,
            (self.processResponsePdu, (cbFun, cbCtx))            
            )

# XXX
# reduce code dublication
# make secret persistent for fast startup
# re-design MIB name spec syntax