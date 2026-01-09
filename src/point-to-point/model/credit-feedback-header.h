/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2024
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Author: Credit-based PFC Enhancement Module
 * Description: Header for credit feedback packets used in the credit-based 
 *              congestion control enhancement module.
 */

#ifndef CREDIT_FEEDBACK_HEADER_H
#define CREDIT_FEEDBACK_HEADER_H

#include <stdint.h>
#include "ns3/header.h"
#include "ns3/buffer.h"

namespace ns3 {

/**
 * \ingroup credit-feedback
 * \brief Header for Credit Feedback Message
 *
 * This header carries congestion information from downstream switches to upstream switches.
 * It includes:
 * - Queue length: Current ingress queue occupancy
 * - Queue gradient: Rate of change of queue length (positive = growing)
 * - Credit value: Suggested credit increment for the upstream port
 * - Port index: The downstream port that generated this feedback
 */
class CreditFeedbackHeader : public Header {
public:
    CreditFeedbackHeader();
    CreditFeedbackHeader(uint32_t queueLen, int16_t gradient, uint16_t creditValue, uint8_t portIndex);
    virtual ~CreditFeedbackHeader();

    // Setters
    void SetQueueLen(uint32_t queueLen);
    void SetGradient(int16_t gradient);
    void SetCreditValue(uint16_t creditValue);
    void SetPortIndex(uint8_t portIndex);

    // Getters
    uint32_t GetQueueLen() const;
    int16_t GetGradient() const;
    uint16_t GetCreditValue() const;
    uint8_t GetPortIndex() const;

    // Header methods
    static TypeId GetTypeId(void);
    virtual TypeId GetInstanceTypeId(void) const;
    virtual void Print(std::ostream &os) const;
    virtual uint32_t GetSerializedSize(void) const;
    virtual void Serialize(Buffer::Iterator start) const;
    virtual uint32_t Deserialize(Buffer::Iterator start);

    // Protocol number for credit feedback (0xFB)
    static const uint8_t PROT_NUMBER = 0xFB;

private:
    uint32_t m_queueLen;      // 4 bytes - Current queue length in bytes
    int16_t m_gradient;       // 2 bytes - Queue change gradient (bytes per interval)
    uint16_t m_creditValue;   // 2 bytes - Suggested credit value (0-1000)
    uint8_t m_portIndex;      // 1 byte  - Port index that generated this feedback
};

} // namespace ns3

#endif /* CREDIT_FEEDBACK_HEADER_H */
