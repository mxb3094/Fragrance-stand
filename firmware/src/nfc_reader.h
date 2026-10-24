#ifndef NFC_READER_H
#define NFC_READER_H

#include <arduino.h>

int tagPresent();

String getScannedUID();

#endif