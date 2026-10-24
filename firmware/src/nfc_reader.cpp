#include "nfc_reader.h"
#include<MFRC522.h>

extern MFRC522 rfid;

int tagPresent()
{
    if(!rfid.PICC_IsNewCardPresent())
    {
        return false;
    }
    if(!rfid.PICC_ReadCardSerial())
    {
        return false;
    }
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return true;
}



String getScannedUID()
{
    String uidString="";

    for(int i=0; i<rfid.uid.size;i++)
    {
        int byte = rfid.uid.uidByte[i];
        String hexByte = String(byte, HEX);
        if (hexByte.length() == 1)
        {
            hexByte = "0" + hexByte;
        }
        uidString += hexByte;
    }

    return uidString;


}