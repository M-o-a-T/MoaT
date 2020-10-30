#ifndef EMB_MAIN_H
#define EMB_MAIN_H

#include <stdarg.h>

#include "moatbus/message.h"

typedef struct _log {
    struct _log *next;
    char buf[0];
} *LOG;
extern LOG logbuf;

void send_serial_msg(BusMessage msg, uint8_t prio);
void send_bus_msg(BusMessage msg, uint8_t prio);

void process_serial_msg(BusMessage msg, uint8_t prio);
char process_bus_msg(BusMessage msg);

void setup_polled();
void loop_polled();

void setup_serial();
void loop_serial();
bool serial_is_idle();

void logger(const char *format, ...);
void vlogger(const char * format, va_list arg);

unsigned int memspace();

#endif
